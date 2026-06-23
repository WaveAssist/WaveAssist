import logging
import requests
import pandas as pd
import time
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dotenv import load_dotenv
from typing import Type, TypeVar, Literal, Optional, Any, BinaryIO
from pydantic import BaseModel
from pathlib import Path
from openai import OpenAI
from datetime import datetime

from waveassist import _config
from waveassist.constants import (
    OPENROUTER_URL,
    OPENROUTER_API_STORED_DATA_KEY,
    UNSUPPORTED_JSON_MODELS_ARRAY,
    LLM_PROVIDER_STORED_DATA_KEY,
    AZURE_OPENAI_CONFIG_STORED_DATA_KEY,
    LLM_MODELS_STORED_DATA_KEY,
    LLM_CREDENTIALS_STORED_DATA_KEY,
    CLAUDE_SETUP_TOKEN_STORED_DATA_KEY,
    RUN_IDLE_STORED_DATA_KEY,
    PROVIDER_OPENROUTER,
    PROVIDER_AZURE,
    PROVIDER_CLAUDE_CLI,
    PROVIDER_CLAUDE_CLI_TOKEN,
    AZURE_API_TYPE_CHAT,
    AZURE_API_TYPE_RESPONSES,
    AZURE_RESPONSES_UNSUPPORTED_KWARGS,
    AZURE_RESPONSES_MIN_OUTPUT_TOKENS,
)
from waveassist.utils import (
    call_post_api,
    call_get_api,
    call_post_api_with_files,
    create_json_prompt,
    parse_json_response,
)

logger = logging.getLogger("waveassist")

__all__ = [
    "init",
    "set_worker_defaults",
    "set_default_environment_key",
    "store_data",
    "fetch_data",
    "publish_dashboard",
    "send_email",
    "fetch_openrouter_credits",
    "check_credits_and_notify",
    "call_llm",
    "mark_run_idle",
    "is_test_run",
    "StoreDataType",
]


# TypeVar for generic type hinting: T represents any Pydantic BaseModel subclass
# This allows call_llm() to return the exact type of the response_model passed in
T = TypeVar('T', bound=BaseModel)


def _conditionally_load_env():
    # Only load .env if UID/project_key aren't set
    if not os.getenv("uid") or not os.getenv("project_key"):
        env_path = Path.cwd() / ".env"  # Use the project root (not library path)
        load_dotenv(dotenv_path=env_path, override=False)


def init(
    token: str = None,
    project_key: str = None,
    environment_key: str = None,
    run_id: str = None,
    check_credits: bool = False,
) -> None:
    _conditionally_load_env()  # Load from .env if it exists

    # Resolve UID/token
    resolved_token = (
        token or os.getenv("uid") or getattr(_config, "DEFAULT_LOGIN_TOKEN", None)
    )

    # Resolve project_key
    resolved_project_key = (
        project_key
        or os.getenv("project_key")
        or getattr(_config, "DEFAULT_PROJECT_KEY", None)
    )

    # Resolve env_key
    resolved_env_key = (
        environment_key
        or os.getenv("environment_key")
        or getattr(_config, "DEFAULT_ENVIRONMENT_KEY", None)
        or f"{resolved_project_key}_default"
        if resolved_project_key
        else None
    )

    # Resolve run_id
    resolved_run_id = (
        run_id or os.getenv("run_id") or getattr(_config, "DEFAULT_RUN_ID", None)
    )

    # Convert run_id to string if it exists
    if resolved_run_id is not None:
        resolved_run_id = str(resolved_run_id)

    # Validate critical keys
    if not resolved_token:
        raise ValueError(
            "WaveAssist init failed: UID is missing. Pass explicitly or set uid in .env."
        )
    if not resolved_project_key:
        raise ValueError(
            "WaveAssist init failed: project key is missing. Pass explicitly or set project_key in .env."
        )

    # Set config
    _config.LOGIN_TOKEN = resolved_token
    _config.PROJECT_KEY = resolved_project_key
    _config.ENVIRONMENT_KEY = resolved_env_key
    _config.RUN_ID = resolved_run_id

    # Check credits if requested
    if check_credits:
        credits_available = str(fetch_data("credits_available", default="1"))
        if credits_available == "0":
            raise RuntimeError("Credits not available, skipping this operation")


def set_worker_defaults(
    token: str = None,
    project_key: str = None,
    environment_key: str = None,
    run_id: str = None,
) -> None:
    """Set default values for login token, project key, environment key, and run_id."""
    _config.DEFAULT_LOGIN_TOKEN = token
    _config.DEFAULT_PROJECT_KEY = project_key
    _config.DEFAULT_ENVIRONMENT_KEY = environment_key
    _config.DEFAULT_RUN_ID = run_id


def set_default_environment_key(key: str) -> None:
    _config.DEFAULT_ENVIRONMENT_KEY = key


# Supported storage data types
StoreDataType = Literal["string", "json", "dataframe"]


def store_data(
    key: str,
    data: Any,
    run_based: bool = False,
    data_type: Optional[StoreDataType] = None,
):
    """
    Serialize the data based on its type and store it in the WaveAssist backend.

    Args:
        key: Storage key.
        data: Value to store (DataFrame, dict, list, or stringable).
        run_based: If True, scope storage to the current run_id.
        data_type: Optional explicit type ("string", "json", "dataframe").
                   If not set, type is inferred from data. When set, data is
                   normalized to that type before storing.

    Returns:
        True if store succeeded, False otherwise.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    format: str
    serialized_data: Any

    if data_type is not None:
        # Caller requested a specific type: normalize data to that type
        if data_type == "dataframe":
            if isinstance(data, pd.DataFrame):
                serialized_data = json.loads(
                    data.to_json(orient="records", date_format="iso")
                )
            elif isinstance(data, (list, dict)):
                serialized_data = pd.DataFrame(data).to_dict(orient="records")
            else:
                serialized_data = pd.DataFrame([{"value": data}]).to_dict(
                    orient="records"
                )
            format = "dataframe"
        elif data_type == "json":
            if isinstance(data, (dict, list)):
                serialized_data = data
            elif isinstance(data, pd.DataFrame):
                serialized_data = json.loads(
                    data.to_json(orient="records", date_format="iso")
                )
            else:
                serialized_data = {"value": str(data)}
            # Ensure JSON-serializable
            json.dumps(serialized_data)
            format = "json"
        else:  # "string"
            serialized_data = str(data)
            format = "string"
    else:
        # Infer type from data and ensure correct serialization
        if isinstance(data, pd.DataFrame):
            format = "dataframe"
            serialized_data = json.loads(
                data.to_json(orient="records", date_format="iso")
            )
        elif isinstance(data, (dict, list)):
            format = "json"
            try:
                json.dumps(data)
                serialized_data = data
            except (TypeError, ValueError):
                serialized_data = str(data)
                format = "string"
        else:
            format = "string"
            serialized_data = str(data)

    payload = {
        "uid": _config.LOGIN_TOKEN,
        "data_type": format,
        "data": serialized_data,
        "project_key": _config.PROJECT_KEY,
        "data_key": str(key),
        "environment_key": _config.ENVIRONMENT_KEY,
        "run_based": "1" if run_based else "0",
    }

    # Add run_id to payload if run_based is True and run_id is set
    if run_based and _config.RUN_ID:
        payload["run_id"] = str(_config.RUN_ID)

    path = "data/set_data_for_key/"
    success, response = call_post_api(path, payload)

    if not success:
        logger.error("Error storing data: %s", response)

    return success


def fetch_data(
    key: str,
    run_based: bool = False,
    default: Any = None,
):
    """
    Retrieve the data stored under `key` from the WaveAssist backend.

    Args:
        key: Storage key.
        run_based: If True, scope lookup to the current run_id.
        default: Value to return when the key is missing, API fails, or
                  the stored type is unsupported/invalid. Not used when
                  the key exists and deserialization succeeds.

    Returns:
        Deserialized data (DataFrame, dict, list, or str) matching the
        stored data_type. Returns `default` on failure or missing key.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    params = {
        "uid": _config.LOGIN_TOKEN,
        "project_key": _config.PROJECT_KEY,
        "data_key": str(key),
        "environment_key": _config.ENVIRONMENT_KEY,
        "run_based": "1" if run_based else "0",
    }

    # Add run_id to params if run_based is True and run_id is set
    if run_based and _config.RUN_ID:
        params["run_id"] = str(_config.RUN_ID)

    path = "data/fetch_data_for_key/"
    success, response = call_get_api(path, params)

    if not success:
        return default

    try:
        # Extract stored format and already-deserialized data
        data_type = response.get("data_type")
        data = response.get("data")

        # Missing or null data
        if data is None and data_type is None:
            return default

        if data_type == "dataframe":
            if data is None:
                return default
            if isinstance(data, pd.DataFrame):
                return data
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame({"value": [data]})
        elif data_type == "json":
            if data is None:
                return default
            if isinstance(data, (dict, list)):
                return data
            # Coerce to list so we always return valid JSON type
            return [data] if data is not None else default
        elif data_type == "string":
            if data is None:
                return default
            return str(data)
        else:
            logger.warning("Unsupported data_type: %s", data_type)
            return default
    except Exception:
        logger.error("fetch_data: unexpected error deserializing key '%s'", key, exc_info=True)
        return default

def publish_dashboard(
    html_content: str,
    data_key: str = "dashboard_html",
    run_based: bool = False,
) -> Optional[str]:
    """
    Store an HTML dashboard and return a public shareable URL.

    Args:
        html_content: Full HTML string for the dashboard page.
        data_key: Storage key (default "dashboard_html").
        run_based: If True, scope to the current run_id.

    Returns:
        The public URL string, or None on failure.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    stored = store_data(data_key, html_content, run_based=run_based, data_type="string")
    if not stored:
        logger.error("publish_dashboard: failed to store HTML content.")
        return None

    payload = {
        "uid": _config.LOGIN_TOKEN,
        "project_key": _config.PROJECT_KEY,
        "environment_key": _config.ENVIRONMENT_KEY,
        "data_key": data_key,
        "run_based": "1" if run_based else "0",
    }
    if run_based and _config.RUN_ID:
        payload["run_id"] = str(_config.RUN_ID)

    success, response = call_post_api("dashboard/generate_link/", payload)
    if not success:
        logger.error("publish_dashboard: failed to generate link — %s", response)
        return None

    token = response.get("data", {}).get("token") if isinstance(response, dict) else None
    if not token:
        logger.error("publish_dashboard: no token in response.")
        return None

    from waveassist.constants import API_BASE_URL
    return f"{API_BASE_URL}/d/{token}/"


# Email validation limits
_SEND_EMAIL_SUBJECT_MAX_LENGTH = 500
_SEND_EMAIL_HTML_MAX_LENGTH = 5_000_000


def _normalize_recipients(value) -> list:
    """Coerce a str | list[str] of recipients into a clean, order-preserving, deduped list.

    Strips whitespace, drops blanks/None, and removes case-insensitive duplicates. Format
    validation is intentionally left to the backend (which validates every address)."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    out, seen = [], set()
    for item in value:
        if item is None:
            continue
        addr = str(item).strip()
        if not addr:
            continue
        if addr.lower() in seen:
            continue
        seen.add(addr.lower())
        out.append(addr)
    return out


def send_email(
    subject: str,
    html_content: str,
    attachment_file: Optional[BinaryIO] = None,
    cc=None,
    bcc=None,
    raise_on_failure: bool = True,
) -> bool:
    """
    Send an email with optional attachment via the WaveAssist backend.

    The primary recipient is always the account owner. Use ``cc``/``bcc`` to copy
    additional recipients (e.g. a per-group digest); ``bcc`` keeps addresses private.

    Args:
        subject: Email subject (non-empty, max 500 chars).
        html_content: HTML body (non-empty, max 5M chars).
        attachment_file: Optional file-like object with .read() and optional .name.
        cc: Optional additional recipient(s), str or list of str (visible to all).
        bcc: Optional additional recipient(s), str or list of str (hidden from others).
        raise_on_failure: If True, raise ValueError/RuntimeError on validation or API failure.

    Returns:
        True if sent successfully, False otherwise (unless raise_on_failure=True).

    Raises:
        RuntimeError: If WaveAssist is not initialized.
        ValueError: If validation fails (empty subject/html, invalid attachment).
        RuntimeError: If API fails and raise_on_failure=True.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    # Input validation
    subject_clean = (subject or "").strip()
    if not subject_clean:
        err = "Subject cannot be empty."
        if raise_on_failure:
            raise ValueError(err)
        logger.error("%s", err)
        return False
    if len(subject_clean) > _SEND_EMAIL_SUBJECT_MAX_LENGTH:
        err = f"Subject too long (max {_SEND_EMAIL_SUBJECT_MAX_LENGTH} chars)."
        if raise_on_failure:
            raise ValueError(err)
        logger.error("%s", err)
        return False

    html_clean = (html_content or "").strip()
    if not html_clean:
        err = "HTML content cannot be empty."
        if raise_on_failure:
            raise ValueError(err)
        logger.error("%s", err)
        return False
    if len(html_clean) > _SEND_EMAIL_HTML_MAX_LENGTH:
        err = f"HTML content too long (max {_SEND_EMAIL_HTML_MAX_LENGTH} chars)."
        if raise_on_failure:
            raise ValueError(err)
        logger.error("%s", err)
        return False

    # Attachment: must be file-like with .read()
    files = None
    if attachment_file is not None:
        if not callable(getattr(attachment_file, "read", None)):
            err = "Attachment must be a file-like object with a .read() method."
            if raise_on_failure:
                raise ValueError(err)
            logger.error("%s", err)
            return False
        file_name = getattr(attachment_file, "name", "attachment")
        files = {"attachment": (file_name, attachment_file)}

    data = {
        "uid": _config.LOGIN_TOKEN,
        "project_key": _config.PROJECT_KEY,
        "subject": subject_clean,
        "html_content": html_clean,
    }

    # Optional carbon-copy recipients; omit the keys entirely when none are given so the
    # backend's owner-only default path is unchanged.
    cc_list = _normalize_recipients(cc)
    if cc_list:
        data["cc"] = ",".join(cc_list)
    bcc_list = _normalize_recipients(bcc)
    if bcc_list:
        data["bcc"] = ",".join(bcc_list)

    path = "sdk/send_email/"
    success = False
    response_msg = None
    max_attempts = 2

    for attempt in range(max_attempts):
        success, response = call_post_api_with_files(path, data, files=files)
        if success:
            break
        response_msg = response if isinstance(response, str) else str(response)
        if attempt < max_attempts - 1:
            time.sleep(1)

    if not success:
        logger.error("Error sending email: %s", response_msg)
        if raise_on_failure:
            raise RuntimeError(response_msg or "Send email failed.")
        return False
    logger.info("Email sent successfully.")
    return True


def fetch_openrouter_credits():
    """Fetch the credit balance for the current project."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )
    path = "/fetch_openrouter_credits/" + _config.LOGIN_TOKEN
    success, response = call_get_api(path, {})
    if not success:
        logger.error("Error fetching credit balance: %s", response)
        return {}
    return response


def check_credits_and_notify(
    required_credits: float,
    assistant_name: str,
) -> bool:
    """
    Check OpenRouter credits via account-level cache and send a one-time notification
    email if insufficient credits are available. Email is sent server-side.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    success, response = call_post_api(
        "sdk/check_account_credits/",
        {
            "uid": _config.LOGIN_TOKEN,
            "project_key": _config.PROJECT_KEY,
            "required_credits": required_credits,
            "assistant_name": assistant_name,
        },
    )

    if not success:
        raise RuntimeError(f"Failed to check credits: {response}")

    data = response.get("data", {})

    if "credits_available" not in data:
        raise RuntimeError("Unexpected response from credits check — 'credits_available' missing.")

    credits_available = data["credits_available"]
    credits_remaining = data.get("credits_remaining", 0)

    if not credits_available:
        logger.warning("[%s] Insufficient credits. Required: %s, Remaining: %s", assistant_name, required_credits, credits_remaining)
    else:
        logger.info("[%s] Sufficient credits available. Required: %s, Remaining: %s", assistant_name, required_credits, credits_remaining)

    return credits_available


def _resolve_claude_cli_model(model: str) -> str:
    """
    Map an OpenRouter/generic model name to a Claude CLI compatible model.

    Conversion: strip provider prefix, replace '.' with '-'.
    e.g. anthropic/claude-sonnet-4.6 → claude-sonnet-4-6
    """
    # Env var override takes highest priority
    env_model = os.environ.get("CLAUDE_CLI_MODEL")
    if env_model:
        return env_model

    # Strip provider prefix (e.g. "anthropic/claude-sonnet-4.6" → "claude-sonnet-4.6")
    if "/" in model:
        model = model.rsplit("/", 1)[1]

    # Not a Claude model — can't convert
    if not model.startswith("claude"):
        raise ValueError(
            f"Claude CLI: non-Claude model '{model}' cannot be auto-converted. "
            f"Set CLAUDE_CLI_MODEL env var to specify a Claude model explicitly."
        )

    # Replace dots with hyphens (OpenRouter uses dots, CLI uses hyphens)
    # e.g. claude-sonnet-4.6 → claude-sonnet-4-6
    return model.replace(".", "-")


def _parse_claude_cli_result(result, response_model: Type[T], model: str) -> T:
    """Parse a `claude -p --output-format json` CompletedProcess into the model.

    The CLI wraps the answer in {"result": "...", ...}; fall back to raw stdout
    if that envelope is absent.
    """
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr}")

    cli_output = json.loads(result.stdout)
    content = cli_output.get("result", result.stdout.strip())
    return parse_json_response(content, response_model, model)


def _call_llm_claude_cli(
    model: str,
    prompt: str,
    response_model: Type[T],
    *,
    use_setup_token: bool = False,
    setup_token: Optional[str] = None,
    **kwargs
) -> T:
    """
    Alternative to call_llm that routes through the Claude Code CLI (`claude -p`).
    Draws on a Claude subscription — no OpenRouter/API credits needed.

    Two auth modes:
      * use_setup_token=False (provider 'claude_cli'): local dev. Inherits the
        host's existing `claude login`; no token, no env override. Original
        behavior, activated by LLM_PROVIDER=claude_cli.
      * use_setup_token=True (provider 'claude_cli_token'): headless on the
        worker fleet. Authenticates with a setup token injected as
        CLAUDE_CODE_OAUTH_TOKEN into a per-call child environment. The token comes
        from `setup_token` when given (e.g. an llm_models registry entry), else
        from the account's 'claude_setup_token' Variable.

    Note: Claude CLI does not support temperature, top_p, or other sampling
    kwargs. Only model, prompt, and response structure are passed through.
    """
    resolved_model = _resolve_claude_cli_model(model)
    json_prompt = create_json_prompt(prompt, response_model)

    # Never pass --bare: bare mode ignores CLAUDE_CODE_OAUTH_TOKEN.
    cmd = [
        "claude", "-p", json_prompt,
        "--output-format", "json",
        "--model", resolved_model,
        "--max-turns", "1",
    ]

    if not use_setup_token:
        # Local dev: inherit the host's `claude login`; no env override.
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return _parse_claude_cli_result(result, response_model, model)

    # Headless auth: explicit registry token wins, else the account's setup-token Variable.
    token = setup_token or fetch_data(CLAUDE_SETUP_TOKEN_STORED_DATA_KEY)
    if not token:
        raise ValueError(
            "Claude setup token not found. Generate one with `claude setup-token` "
            "and store it: "
            "waveassist.store_data('claude_setup_token', 'sk-ant-oat01-...')"
        )

    # Per-call isolated config home. Concurrent `claude` runs corrupt a shared
    # ~/.claude.json (no file locking) and could bleed sessions across tenants on
    # the shared worker, so each invocation gets its own throwaway CLAUDE_CONFIG_DIR.
    config_dir = tempfile.mkdtemp(prefix="wa_claude_")
    try:
        env = os.environ.copy()
        env["CLAUDE_CODE_OAUTH_TOKEN"] = str(token)
        env["CLAUDE_CONFIG_DIR"] = config_dir
        # ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN outrank the OAuth token in
        # Claude's auth precedence; leaving them set would silently switch to
        # per-token API billing instead of the subscription.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, env=env
        )
        return _parse_claude_cli_result(result, response_model, model)
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


def _resolve_llm_provider() -> str:
    """Resolve the active LLM provider.

    Precedence: LLM_PROVIDER env var (dev override) > server-stored
    'llm_provider' value > default OpenRouter.
    """
    provider = (
        os.environ.get("LLM_PROVIDER")
        or fetch_data(LLM_PROVIDER_STORED_DATA_KEY)
        or PROVIDER_OPENROUTER
    )
    return str(provider).strip().lower()


def _resolve_llm_client(provider: str, kwargs: dict) -> OpenAI:
    """Build the OpenAI-compatible client for a hosted provider.

    Handles 'azure' and 'openrouter' (the default). Mutates kwargs in place for
    provider-specific quirks. The 'claude_cli' provider is handled separately in
    call_llm and never reaches here.
    """
    if provider == PROVIDER_AZURE:
        config = fetch_data(AZURE_OPENAI_CONFIG_STORED_DATA_KEY)
        # fetch_data may wrap a stored value in a list; unwrap to the dict.
        if isinstance(config, list):
            config = config[0] if config else None
        if not isinstance(config, dict) or not config.get("api_key") or not config.get("endpoint"):
            raise ValueError(
                "Azure OpenAI config not found or incomplete. Please store it using "
                "waveassist.store_data('azure_openai_config', "
                "{'api_key': '...', 'endpoint': 'https://<resource>.openai.azure.com/'})"
            )
        base_url = config["endpoint"].rstrip("/") + "/openai/v1/"
        # Newer Azure models require max_completion_tokens instead of max_tokens.
        if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return OpenAI(api_key=config["api_key"], base_url=base_url)

    # Default: OpenRouter
    api_key = fetch_data(OPENROUTER_API_STORED_DATA_KEY)
    if not api_key:
        raise ValueError(
            "OpenRouter API key not found. Please store it using waveassist.store_data('open_router_key', 'your_api_key')"
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_URL)


def _azure_api_type(config: dict) -> str:
    """Which Azure API surface to use for this config.

    Read from the optional ``api_type`` field of ``azure_openai_config``:
      - ``"chat_completions"`` (default) -> client.chat.completions.create
      - ``"responses"``                  -> client.responses.parse (reasoning/pro models)

    Reasoning / "pro" models (gpt-5.x-pro, o1/o3, ...) are not served on
    chat.completions, so those deployments must set ``api_type="responses"``.
    """
    api_type = str(config.get("api_type") or AZURE_API_TYPE_CHAT).strip().lower()
    if api_type not in (AZURE_API_TYPE_CHAT, AZURE_API_TYPE_RESPONSES):
        raise ValueError(
            f"Invalid azure_openai_config 'api_type': {api_type!r}. "
            f"Expected '{AZURE_API_TYPE_CHAT}' or '{AZURE_API_TYPE_RESPONSES}'."
        )
    return api_type


def _call_llm_responses(
    client: OpenAI,
    model: str,
    prompt: str,
    response_model: Type[T],
    kwargs: dict,
) -> T:
    """Azure Responses API path for reasoning / "pro" models.

    Uses strict structured outputs (``text_format=response_model``), which the
    SDK enforces via a JSON schema and returns as an already-validated pydantic
    object. Falls back to soft-parsing the raw text if the model returns no
    parsed output. Transport errors are retried once, mirroring the chat path.
    """
    # The Responses API uses max_output_tokens; translate the chat-style args.
    max_out = kwargs.pop("max_output_tokens", None)
    if max_out is None:
        max_out = kwargs.pop("max_completion_tokens", None)
    if max_out is None:
        max_out = kwargs.pop("max_tokens", None)
    # response_format is a chat.completions concept; not accepted here.
    kwargs.pop("response_format", None)
    # Reasoning / "pro" models reject sampling params (temperature, top_p, ...);
    # callers pass them blindly, so drop them rather than 400.
    for unsupported in AZURE_RESPONSES_UNSUPPORTED_KWARGS:
        kwargs.pop(unsupported, None)
    if max_out is not None:
        # Reasoning tokens count against this budget; floor it so a value sized
        # for chat output doesn't truncate the response.
        kwargs["max_output_tokens"] = max(max_out, AZURE_RESPONSES_MIN_OUTPUT_TOKENS)

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            response = client.responses.parse(
                model=model,
                input=prompt,
                text_format=response_model,
                **kwargs,
            )
            parsed = response.output_parsed
            if parsed is not None:
                return parsed
            # No structured object returned; soft-parse the text output.
            return parse_json_response(response.output_text, response_model, model)
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"LLM API call failed after {max_attempts} attempts: {str(e)}"
            ) from e

    raise RuntimeError("LLM API call failed: maximum attempts reached")


def _azure_base(api_base: str) -> str:
    """Normalize an Azure endpoint to the OpenAI-compatible v1 base the client expects. Accepts a bare
    resource URL ('https://x.openai.azure.com/') or one already ending in '/openai/v1'."""
    b = (api_base or "").rstrip("/")
    if not b.endswith("/openai/v1"):
        b = b + "/openai/v1"
    return b + "/"


def _resolve_model_entry(model: str):
    """Look up `model` (an alias) in the per-project `llm_models` registry. Returns a self-contained,
    credential-resolved entry dict, or None when there is no registry / no matching entry — in which
    case call_llm falls back to the legacy global resolution (which itself defaults to OpenRouter).
    An entry may carry creds inline, or point at a shared credential via {"credential": "<ref>"}
    resolved from `llm_credentials` (inline entry fields win over the shared block)."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        return None
    try:
        registry = fetch_data(LLM_MODELS_STORED_DATA_KEY)
    except Exception:
        return None
    if isinstance(registry, list):
        registry = registry[0] if registry else None
    if not isinstance(registry, dict):
        return None
    entry = registry.get(model)
    if not isinstance(entry, dict):
        return None
    cred_ref = entry.get("credential")
    if cred_ref:
        creds = fetch_data(LLM_CREDENTIALS_STORED_DATA_KEY)
        if isinstance(creds, list):
            creds = creds[0] if creds else {}
        shared = creds.get(cred_ref, {}) if isinstance(creds, dict) else {}
        if isinstance(shared, dict):
            return {**shared, **entry}
    return dict(entry)


def _call_llm_chat(client, model, prompt, response_model, should_retry, kwargs):
    """Shared OpenAI-compatible chat.completions path (OpenRouter + Azure chat models): JSON-format
    response, soft-parse, one transport retry, plus one optional format retry when should_retry."""
    json_prompt = create_json_prompt(prompt, response_model)
    kwargs.pop("response_format", None)
    response_format = {"type": "json_object"}
    if any(x in model.lower() for x in UNSUPPORTED_JSON_MODELS_ARRAY):
        response_format = None

    max_attempts = 2
    format_error_retried = False
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": json_prompt}],
                response_format=response_format,
                **kwargs
            )
            content = response.choices[0].message.content
            try:
                return parse_json_response(content, response_model, model)
            except ValueError:
                if should_retry and not format_error_retried:
                    format_error_retried = True
                    json_prompt = create_json_prompt(
                        prompt + "\n\nIMPORTANT: Your previous response was invalid JSON. You must output ONLY valid JSON matching the schema, with no explanations or other text.",
                        response_model
                    )
                    if 'temperature' not in kwargs:
                        kwargs['temperature'] = 0.2
                    continue
                raise
        except ValueError:
            raise
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"LLM API call failed after {max_attempts} attempts: {str(e)}"
            ) from e
    raise RuntimeError("LLM API call failed: maximum attempts reached")


def _call_llm_via_entry(entry, alias, prompt, response_model, should_retry, kwargs):
    """Dispatch one call using a self-contained `llm_models` entry: provider + model + creds + (azure)
    api_type all come from the entry, so different models on one project can use different providers."""
    provider = (entry.get("provider") or "").strip().lower()
    model_id = entry.get("model") or alias

    if provider in (PROVIDER_CLAUDE_CLI, PROVIDER_CLAUDE_CLI_TOKEN):
        return _call_llm_claude_cli(
            model_id, prompt, response_model,
            use_setup_token=(provider == PROVIDER_CLAUDE_CLI_TOKEN),
            setup_token=entry.get("token") or entry.get("api_key"),
            **kwargs,
        )

    if provider == PROVIDER_AZURE:
        api_key = entry.get("api_key") or entry.get("token")
        if not api_key or not entry.get("api_base"):
            raise ValueError(f"llm_models['{alias}']: azure requires 'api_base' and 'api_key'.")
        client = OpenAI(api_key=api_key, base_url=_azure_base(entry["api_base"]))
        if (entry.get("api_type") or "").strip().lower() == AZURE_API_TYPE_RESPONSES:
            return _call_llm_responses(client, model_id, prompt, response_model, kwargs)
        # Newer Azure chat models require max_completion_tokens instead of max_tokens.
        if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return _call_llm_chat(client, model_id, prompt, response_model, should_retry, kwargs)

    if provider in ("", PROVIDER_OPENROUTER):
        api_key = entry.get("api_key") or fetch_data(OPENROUTER_API_STORED_DATA_KEY)
        if not api_key:
            raise ValueError(
                f"llm_models['{alias}']: OpenRouter needs an 'api_key' or a stored open_router_key."
            )
        client = OpenAI(api_key=api_key, base_url=OPENROUTER_URL)
        return _call_llm_chat(client, model_id, prompt, response_model, should_retry, kwargs)

    raise ValueError(f"llm_models['{alias}']: unknown provider '{provider}'.")


def call_llm(
    model: str,
    prompt: str,
    response_model: Type[T],
    should_retry: bool = False,
    **kwargs
) -> T:
    """
    Call an LLM via OpenRouter and return structured responses.
    Uses JSON response format and soft parsing for reliable structured output.
    
    Args:
        model: The model name to use (e.g., "gpt-4o", "anthropic/claude-3.5-sonnet")
        prompt: The prompt to send to the LLM
        response_model: A Pydantic model class that defines the structure of the response
        should_retry: If True, will retry once for format/JSON errors. Defaults to False.
                     Transport errors (network, 5xx, 429, timeouts) are always retried once.
        **kwargs: Additional arguments to pass to the chat completion call (e.g., max_tokens, extra_body)
    
    Returns:
        An instance of the response_model with structured data from the LLM
    
    Raises:
        RuntimeError: If the LLM API call fails (network, HTTP errors, timeouts)
        ValueError: If the LLM call succeeded but JSON extraction/validation failed
    
    Example:
        from pydantic import BaseModel
        class UserInfo(BaseModel):
            name: str
            age: int
            email: str
        # With additional parameters and retry enabled
        result = waveassist.call_llm(
            model="<model_name>",
            prompt="Extract user info: John Doe, 30, john@example.com",
            response_model=UserInfo,
            should_retry=True,
            max_tokens=3000,
            extra_body={"web_search_options": {"search_context_size": "medium"}})
    """
    # 1) Explicit env override (local dev) wins globally: route to the Claude CLI.
    env_provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if env_provider in (PROVIDER_CLAUDE_CLI, PROVIDER_CLAUDE_CLI_TOKEN):
        return _call_llm_claude_cli(
            model, prompt, response_model,
            use_setup_token=(env_provider == PROVIDER_CLAUDE_CLI_TOKEN),
            **kwargs,
        )

    # 2) Per-model registry: a self-contained entry carries its own provider + creds + api_type, so
    #    one project can mix Azure / Claude / OpenRouter per model. Absent (the common OpenRouter
    #    case) -> fall through to the legacy global resolution below.
    entry = _resolve_model_entry(model)
    if entry is not None:
        return _call_llm_via_entry(entry, model, prompt, response_model, should_retry, kwargs)

    # 3) Legacy global resolution (backward compatible): stored llm_provider / azure_openai_config,
    #    else OpenRouter. Unchanged for any project without an llm_models registry.
    provider = _resolve_llm_provider()
    if provider in (PROVIDER_CLAUDE_CLI, PROVIDER_CLAUDE_CLI_TOKEN):
        return _call_llm_claude_cli(
            model, prompt, response_model,
            use_setup_token=(provider == PROVIDER_CLAUDE_CLI_TOKEN),
            **kwargs,
        )

    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    # Build the OpenAI-compatible client for the configured hosted provider.
    client = _resolve_llm_client(provider, kwargs)

    # Azure reasoning / "pro" models route through the Responses API instead of
    # chat.completions, selected explicitly via azure_openai_config["api_type"].
    if provider == PROVIDER_AZURE:
        azure_config = fetch_data(AZURE_OPENAI_CONFIG_STORED_DATA_KEY)
        if isinstance(azure_config, list):
            azure_config = azure_config[0] if azure_config else {}
        if _azure_api_type(azure_config or {}) == AZURE_API_TYPE_RESPONSES:
            return _call_llm_responses(client, model, prompt, response_model, kwargs)

    return _call_llm_chat(client, model, prompt, response_model, should_retry, kwargs)


def mark_run_idle() -> bool:
    """Mark the CURRENT run as idle — it executed but did no meaningful work (e.g. found no new PR,
    ran a silent security scan, or skipped a cycle). Call this on your node's "nothing to do" branch,
    the same way you call ``store_data("display_output", ...)`` for output.

    It writes a tiny run-scoped flag (``run_idle``); the dashboard collapses idle runs into a single
    heartbeat instead of listing each one. A run that does real work simply never calls this — the
    flag's ABSENCE means "did work" and the run is shown normally. A FAILED run is always shown
    regardless of this flag, so a crash that never reaches this call cannot be mislabeled as idle.

    ``display_output`` is untouched and stays purely presentational, so an idle run can still show a
    rich "all clear" message when expanded.

    Returns True on success, False otherwise.
    """
    return store_data(RUN_IDLE_STORED_DATA_KEY, "1", run_based=True, data_type="string")


_IS_TEST_RUN_KEY = "_is_test_run"


def is_test_run() -> bool:
    """Return True if the current run is a dry/test run. Backend sets this via store_data."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise RuntimeError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )
    flag = fetch_data(_IS_TEST_RUN_KEY, default=False)
    # fetch_data wraps scalar JSON values in a list — unwrap if needed.
    if isinstance(flag, list):
        flag = flag[0] if flag else False
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, str):
        return flag.lower() in ("1", "true", "yes")
    if flag is None:
        return False
    return bool(flag)
