import logging
import requests
import pandas as pd
import time
import json
import os
from dotenv import load_dotenv
from typing import Type, TypeVar, Literal, Optional, Any, BinaryIO
from pydantic import BaseModel
from pathlib import Path
from openai import OpenAI
from openai import (
    APIError,
    APIConnectionError,
    RateLimitError,
    Timeout as OpenAITimeout,
)
from datetime import datetime

from waveassist import _config
from waveassist.constants import (
    OPENROUTER_URL,
    OPENROUTER_API_STORED_DATA_KEY,
    UNSUPPORTED_JSON_MODELS_ARRAY,
)
from waveassist.utils import (
    call_post_api,
    call_get_api,
    call_post_api_with_files,
    create_json_prompt,
    parse_json_response,
    get_email_template_credits_limit_reached,
    WaveAssistError,
    WaveAssistNotInitializedError,
    WaveAssistEmailError,
    LLMCallError,
    LLMFormatError,
)

logger = logging.getLogger("waveassist")

__all__ = [
    "init",
    "set_worker_defaults",
    "set_default_environment_key",
    "store_data",
    "fetch_data",
    "send_email",
    "fetch_openrouter_credits",
    "check_credits_and_notify",
    "call_llm",
    "StoreDataType",
    "WaveAssistError",
    "WaveAssistNotInitializedError",
    "WaveAssistEmailError",
    "LLMCallError",
    "LLMFormatError",
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
        raise WaveAssistNotInitializedError(
            "WaveAssist init failed: UID is missing. Pass explicitly or set uid in .env."
        )
    if not resolved_project_key:
        raise WaveAssistNotInitializedError(
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
            raise WaveAssistNotInitializedError("Credits not available, skipping this operation")


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
        raise WaveAssistNotInitializedError(
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
        raise WaveAssistNotInitializedError(
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

    # Extract stored format and already-deserialized data
    data_type = response.get("data_type")
    data = response.get("data")

    # Missing or null data
    if data is None and data_type is None:
        return default

    try:
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
    except (TypeError, ValueError):
        return default

# Email validation limits
_SEND_EMAIL_SUBJECT_MAX_LENGTH = 500
_SEND_EMAIL_HTML_MAX_LENGTH = 5_000_000


def send_email(
    subject: str,
    html_content: str,
    attachment_file: Optional[BinaryIO] = None,
    raise_on_failure: bool = True,
) -> bool:
    """
    Send an email with optional attachment via the WaveAssist backend.

    Args:
        subject: Email subject (non-empty, max 500 chars).
        html_content: HTML body (non-empty, max 5M chars).
        attachment_file: Optional file-like object with .read() and optional .name.
        raise_on_failure: If True, raise WaveAssistEmailError on validation or API failure.

    Returns:
        True if sent successfully, False otherwise (unless raise_on_failure=True).

    Raises:
        WaveAssistNotInitializedError: If WaveAssist is not initialized.
        WaveAssistEmailError: If validation fails or API fails and raise_on_failure=True.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise WaveAssistNotInitializedError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    # Input validation
    subject_clean = (subject or "").strip()
    if not subject_clean:
        err = "Subject cannot be empty."
        if raise_on_failure:
            raise WaveAssistEmailError(err)
        logger.error("%s", err)
        return False
    if len(subject_clean) > _SEND_EMAIL_SUBJECT_MAX_LENGTH:
        err = f"Subject too long (max {_SEND_EMAIL_SUBJECT_MAX_LENGTH} chars)."
        if raise_on_failure:
            raise WaveAssistEmailError(err)
        logger.error("%s", err)
        return False

    html_clean = (html_content or "").strip()
    if not html_clean:
        err = "HTML content cannot be empty."
        if raise_on_failure:
            raise WaveAssistEmailError(err)
        logger.error("%s", err)
        return False
    if len(html_clean) > _SEND_EMAIL_HTML_MAX_LENGTH:
        err = f"HTML content too long (max {_SEND_EMAIL_HTML_MAX_LENGTH} chars)."
        if raise_on_failure:
            raise WaveAssistEmailError(err)
        logger.error("%s", err)
        return False

    # Attachment: must be file-like with .read()
    files = None
    if attachment_file is not None:
        if not callable(getattr(attachment_file, "read", None)):
            err = "Attachment must be a file-like object with a .read() method."
            if raise_on_failure:
                raise WaveAssistEmailError(err)
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
            raise WaveAssistEmailError(response_msg or "Send email failed.")
        return False
    logger.info("Email sent successfully.")
    return True


def fetch_openrouter_credits():
    """Fetch the credit balance for the current project."""
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise WaveAssistNotInitializedError(
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
    Check OpenRouter credits and send an email notification if insufficient credits are available.
    """
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise WaveAssistNotInitializedError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    # Fetch current credit balance
    credits_data = fetch_openrouter_credits()

    # Check if the API call failed (empty dict or missing key)
    if not credits_data or "limit_remaining" not in credits_data:
        raise WaveAssistError("Failed to fetch OpenRouter credits. Unable to determine credit balance.")
    
    credits_remaining = float(credits_data.get("limit_remaining", 0))
    
    # Check if sufficient credits are available
    if required_credits > credits_remaining:
        # Fetch current failure count
        failure_count = int(fetch_data("failure_count") or 0)
        
        # Only send email if we haven't sent it 3 times already
        if failure_count < 3:
            # Generate email content using template from constants
            html_content = get_email_template_credits_limit_reached(
                assistant_name=assistant_name,
                required_credits=required_credits,
                credits_remaining=credits_remaining
            )
            
            # Generate email subject
            logger.warning("Insufficient credits. Sending notification email.")
            email_subject = f"{assistant_name} - Unavailable - Credit Limit Reached"
            send_email(subject=email_subject, html_content=html_content)
            
            # Increment and store failure count
            failure_count += 1
            store_data('failure_count', str(failure_count))
        else:
            logger.warning("Insufficient credits. Email notification limit reached (3 emails already sent).")
        
        store_data('credits_available', "0") # Set credits_available to 0 to prevent further operations
        
        return False
    else:
        logger.info("Sufficient credits available. Required: %s, Remaining: %s", required_credits, credits_remaining)
        store_data('credits_available', "1") # Set credits_available to 1 to allow further operations
        store_data('failure_count', "0") # Reset failure count on success
        return True


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
        LLMCallError: If the LLM API call itself fails (network, HTTP errors, timeouts)
        LLMFormatError: If the LLM call succeeded but JSON extraction/validation failed
    
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
    if not _config.LOGIN_TOKEN or not _config.PROJECT_KEY:
        raise WaveAssistNotInitializedError(
            "WaveAssist is not initialized. Please call waveassist.init(...) first."
        )

    # Fetch API key from WaveAssist data storage
    api_key = fetch_data(OPENROUTER_API_STORED_DATA_KEY)
    if not api_key:
        raise WaveAssistError(
            "OpenRouter API key not found. Please store it using waveassist.store_data('open_router_key', 'your_api_key')"
        )
    
    # Initialize OpenAI client with OpenRouter
    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_URL
    )
    
    # Create prompt with JSON structure instructions
    json_prompt = create_json_prompt(prompt, response_model)
    
    # Remove response_format from kwargs to avoid duplicate
    kwargs.pop("response_format", None)
    
    # Check if model supports JSON format
    response_format = {"type": "json_object"}
    
    # Check if model is in the unsupported JSON models array
    if any(x in model.lower() for x in UNSUPPORTED_JSON_MODELS_ARRAY):
        response_format = None 
    
    # Transport errors that should always be retried once
    transport_errors = (APIError, APIConnectionError, RateLimitError, OpenAITimeout)
    
    # Attempt the API call with retry logic
    # For transport errors: always retry once (max 2 attempts total)
    # For format errors: retry once if should_retry=True (max 2 attempts total)
    max_attempts = 2
    format_error_retried = False
    
    for attempt in range(max_attempts):
        try:
            # Make API call with JSON response format
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": json_prompt}],
                response_format=response_format,
                **kwargs
            )
            
            # Extract and parse the response
            content = response.choices[0].message.content
            
            try:
                return parse_json_response(content, response_model, model)
            except LLMFormatError as format_error:
                # Format error - only retry if should_retry=True and haven't retried yet
                if should_retry and not format_error_retried:
                    format_error_retried = True
                    # Strengthen the prompt for retry
                    json_prompt = create_json_prompt(
                        prompt + "\n\nIMPORTANT: Your previous response was invalid JSON. You must output ONLY valid JSON matching the schema, with no explanations or other text.",
                        response_model
                    )
                    # Lower temperature if not already set to improve consistency
                    if 'temperature' not in kwargs:
                        kwargs['temperature'] = 0.2
                    continue
                else:
                    # No retry allowed or already retried, raise the error
                    raise
                    
        except transport_errors as e:
            # Transport error - always retry once (unless this is already the retry)
            if attempt < max_attempts - 1:
                # Exponential backoff: wait 1 second, then 2 seconds
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                # Already retried, raise the error
                raise LLMCallError(
                    f"LLM API call failed after {max_attempts} attempts: {str(e)}"
                ) from e
        except Exception as e:
            # Other unexpected errors - don't retry, convert to LLMCallError
            raise LLMCallError(
                f"Unexpected error during LLM API call: {str(e)}"
            ) from e
    
    # Should never reach here, but handle edge case
    raise LLMCallError("LLM API call failed: maximum attempts reached")
