"""
Tests for LLM provider routing in call_llm:
  - provider resolution (env > server > default)
  - hosted client construction for openrouter / azure
  - azure config validation and max_tokens -> max_completion_tokens rename
  - claude_cli routing (local CLI, no OpenAI client)
"""
import sys
import os
import json
from types import SimpleNamespace

# Add the parent directory to sys.path so we can import waveassist
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from pydantic import BaseModel

import waveassist
from waveassist import _config
from waveassist.constants import (
    OPENROUTER_URL,
    OPENROUTER_API_STORED_DATA_KEY,
    LLM_PROVIDER_STORED_DATA_KEY,
    AZURE_OPENAI_CONFIG_STORED_DATA_KEY,
    CLAUDE_SETUP_TOKEN_STORED_DATA_KEY,
)


class FakeOpenAI:
    """Stand-in for openai.OpenAI that records constructor kwargs."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def store(monkeypatch):
    """In-memory backing for fetch_data; returns the dict to populate per test."""
    data = {}

    def fake_fetch_data(key, run_based=False, default=None):
        return data.get(key, default)

    monkeypatch.setattr(waveassist, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(waveassist, "OpenAI", FakeOpenAI)
    # Ensure no stray env override leaks in from the environment.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    return data


# ----------------------- provider resolution -----------------------

def test_provider_defaults_to_openrouter(store):
    assert waveassist._resolve_llm_provider() == "openrouter"


def test_provider_from_server_value(store):
    store[LLM_PROVIDER_STORED_DATA_KEY] = "Azure"  # normalized
    assert waveassist._resolve_llm_provider() == "azure"


def test_env_overrides_server_and_short_circuits(monkeypatch):
    # fetch_data must NOT be called when the env var is set.
    def boom(*a, **k):
        raise AssertionError("fetch_data should not be called when LLM_PROVIDER is set")

    monkeypatch.setattr(waveassist, "fetch_data", boom)
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli")
    assert waveassist._resolve_llm_provider() == "claude_cli"


# ----------------------- openrouter client -----------------------

def test_openrouter_client(store):
    store[OPENROUTER_API_STORED_DATA_KEY] = "or-key-123"
    client = waveassist._resolve_llm_client("openrouter", {})
    assert isinstance(client, FakeOpenAI)
    assert client.kwargs["api_key"] == "or-key-123"
    assert client.kwargs["base_url"] == OPENROUTER_URL


def test_openrouter_missing_key_raises(store):
    with pytest.raises(ValueError, match="OpenRouter API key not found"):
        waveassist._resolve_llm_client("openrouter", {})


# ----------------------- azure client -----------------------

def test_azure_client_builds_v1_base_url(store):
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "az-key",
        "endpoint": "https://mom.openai.azure.com/",
    }
    client = waveassist._resolve_llm_client("azure", {})
    assert client.kwargs["api_key"] == "az-key"
    assert client.kwargs["base_url"] == "https://mom.openai.azure.com/openai/v1/"


def test_azure_config_unwrapped_from_list(store):
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = [
        {"api_key": "az-key", "endpoint": "https://mom.openai.azure.com"}
    ]
    client = waveassist._resolve_llm_client("azure", {})
    # endpoint has no trailing slash here; base_url must still be well-formed.
    assert client.kwargs["base_url"] == "https://mom.openai.azure.com/openai/v1/"


@pytest.mark.parametrize("config", [None, {}, {"api_key": "x"}, {"endpoint": "y"}])
def test_azure_missing_or_incomplete_config_raises(store, config):
    if config is not None:
        store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = config
    with pytest.raises(ValueError, match="Azure OpenAI config not found"):
        waveassist._resolve_llm_client("azure", {})


def test_azure_renames_max_tokens(store):
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "az-key",
        "endpoint": "https://mom.openai.azure.com/",
    }
    kwargs = {"max_tokens": 1234}
    waveassist._resolve_llm_client("azure", kwargs)
    assert "max_tokens" not in kwargs
    assert kwargs["max_completion_tokens"] == 1234


def test_azure_does_not_override_existing_max_completion_tokens(store):
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "az-key",
        "endpoint": "https://mom.openai.azure.com/",
    }
    kwargs = {"max_tokens": 10, "max_completion_tokens": 99}
    waveassist._resolve_llm_client("azure", kwargs)
    # Caller's explicit max_completion_tokens wins; max_tokens left untouched.
    assert kwargs["max_completion_tokens"] == 99
    assert kwargs["max_tokens"] == 10


# ----------------------- claude_cli routing -----------------------

class _Dummy(BaseModel):
    ok: bool


def test_call_llm_routes_to_claude_cli(monkeypatch):
    sentinel = _Dummy(ok=True)
    calls = {}

    def fake_cli(model, prompt, response_model, **kwargs):
        calls["model"] = model
        return sentinel

    def no_openai(**kwargs):
        raise AssertionError("OpenAI client must not be built for claude_cli")

    monkeypatch.setattr(waveassist, "_call_llm_claude_cli", fake_cli)
    monkeypatch.setattr(waveassist, "OpenAI", no_openai)
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli")

    result = waveassist.call_llm("gpt-5.4", "hi", _Dummy)
    assert result is sentinel
    assert calls["model"] == "gpt-5.4"


# ----------------------- azure api_type resolution -----------------------

def test_azure_api_type_defaults_to_chat_completions(store):
    cfg = {"api_key": "k", "endpoint": "https://x.openai.azure.com/"}
    assert waveassist._azure_api_type(cfg) == "chat_completions"


def test_azure_api_type_responses_normalized(store):
    cfg = {"api_key": "k", "endpoint": "https://x.openai.azure.com/", "api_type": " Responses "}
    assert waveassist._azure_api_type(cfg) == "responses"


def test_azure_api_type_invalid_raises(store):
    cfg = {"api_key": "k", "endpoint": "https://x.openai.azure.com/", "api_type": "rest"}
    with pytest.raises(ValueError, match="api_type"):
        waveassist._azure_api_type(cfg)


# ----------------------- azure responses vs chat routing -----------------------

class _RecordingClient:
    """Fake OpenAI client that records which API surface call_llm invoked."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.responses = self._Responses(self)
        self.chat = SimpleNamespace(completions=self._ChatCompletions(self))

    class _Responses:
        def __init__(self, parent):
            self.parent = parent

        def parse(self, **kw):
            self.parent.calls.append(("responses.parse", kw))
            return SimpleNamespace(output_parsed=_Dummy(ok=True), output_text='{"ok": true}')

    class _ChatCompletions:
        def __init__(self, parent):
            self.parent = parent

        def create(self, **kw):
            self.parent.calls.append(("chat.completions.create", kw))
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )


@pytest.fixture
def azure_routing(monkeypatch, store):
    """Azure provider wired to a recording client; returns (store, created clients)."""
    created = []

    def factory(**kwargs):
        client = _RecordingClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(waveassist, "OpenAI", factory)
    monkeypatch.setattr(_config, "LOGIN_TOKEN", "tok")
    monkeypatch.setattr(_config, "PROJECT_KEY", "proj")
    store[LLM_PROVIDER_STORED_DATA_KEY] = "azure"
    return store, created


def test_call_llm_azure_responses_uses_responses_api(azure_routing):
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
        "api_type": "responses",
    }

    # Use a value above the floor so this test checks translation, not flooring.
    result = waveassist.call_llm("gpt-5.4-pro", "hello", _Dummy, max_tokens=10000)

    assert isinstance(result, _Dummy) and result.ok is True
    client = created[-1]
    assert [c[0] for c in client.calls] == ["responses.parse"]
    _, kw = client.calls[0]
    assert kw["text_format"] is _Dummy
    # Responses API takes max_output_tokens, never chat-only token args.
    assert kw["max_output_tokens"] == 10000
    assert "max_tokens" not in kw and "max_completion_tokens" not in kw


def test_call_llm_azure_chat_completions_is_default(azure_routing):
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
    }

    result = waveassist.call_llm("gpt-5.4", "hello", _Dummy)

    assert isinstance(result, _Dummy)
    client = created[-1]
    assert [c[0] for c in client.calls] == ["chat.completions.create"]


def test_responses_path_drops_unsupported_sampling_params(azure_routing):
    # Reasoning / "pro" models reject temperature, top_p, penalties, etc.
    # Callers (GitZoid, templates) pass these blindly; the responses path must
    # strip them rather than 400.
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
        "api_type": "responses",
    }

    result = waveassist.call_llm(
        "gpt-5.4-pro",
        "hi",
        _Dummy,
        temperature=0.5,
        top_p=0.9,
        presence_penalty=0.1,
        frequency_penalty=0.2,
        max_tokens=300,
    )

    assert isinstance(result, _Dummy)
    _, kw = created[-1].calls[0]
    for bad in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
        assert bad not in kw, f"{bad} must not be forwarded to responses.parse"
    # 300 is below the floor; see test_responses_path_floors_small_max_output_tokens.


def test_responses_path_floors_small_max_output_tokens(azure_routing):
    # Reasoning models spend max_output_tokens on hidden reasoning first, so a
    # small caller value truncates -> hard fail. The responses path raises it.
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
        "api_type": "responses",
    }

    waveassist.call_llm("gpt-5.4-pro", "hi", _Dummy, max_tokens=1200)

    _, kw = created[-1].calls[0]
    assert kw["max_output_tokens"] == 8000  # floored up from 1200


def test_responses_path_preserves_large_max_output_tokens(azure_routing):
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
        "api_type": "responses",
    }

    waveassist.call_llm("gpt-5.4-pro", "hi", _Dummy, max_tokens=20000)

    _, kw = created[-1].calls[0]
    assert kw["max_output_tokens"] == 20000  # above floor, untouched


def test_responses_path_imposes_no_limit_when_unset(azure_routing):
    # Caller passed no token arg -> don't invent a cap (the model's default is
    # large; capping at the floor could truncate where it otherwise wouldn't).
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k",
        "endpoint": "https://x.openai.azure.com/",
        "api_type": "responses",
    }

    waveassist.call_llm("gpt-5.4-pro", "hi", _Dummy)

    _, kw = created[-1].calls[0]
    assert "max_output_tokens" not in kw


# --------------- claude_cli_token (setup-token, headless on the fleet) ---------------
# Same `claude -p` subprocess as claude_cli, but authenticated by the account's
# setup token (a Variable) injected into the child env, with an isolated config
# dir and scrubbed conflicting auth. Provider value: "claude_cli_token".


def _fake_claude_run(captured):
    """Stand-in for subprocess.run that records cmd/kwargs and returns the
    `claude -p --output-format json` envelope ({"result": "<json string>"})."""
    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"result": '{"ok": true}'}),
            stderr="",
        )
    return fake_run


def test_call_llm_routes_to_claude_cli_token(monkeypatch):
    """provider 'claude_cli_token' routes to the CLI with use_setup_token=True."""
    sentinel = _Dummy(ok=True)
    calls = {}

    def fake_cli(model, prompt, response_model, **kwargs):
        calls["model"] = model
        calls["use_setup_token"] = kwargs.get("use_setup_token")
        return sentinel

    def no_openai(**kwargs):
        raise AssertionError("OpenAI client must not be built for claude_cli_token")

    monkeypatch.setattr(waveassist, "_call_llm_claude_cli", fake_cli)
    monkeypatch.setattr(waveassist, "OpenAI", no_openai)
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli_token")

    result = waveassist.call_llm("anthropic/claude-sonnet-4.6", "hi", _Dummy)
    assert result is sentinel
    assert calls["use_setup_token"] is True


def test_call_llm_local_claude_cli_routes_without_setup_token(monkeypatch):
    """existing 'claude_cli' provider must route with use_setup_token False (host login)."""
    calls = {}

    def fake_cli(model, prompt, response_model, **kwargs):
        calls["use_setup_token"] = kwargs.get("use_setup_token", False)
        return _Dummy(ok=True)

    monkeypatch.setattr(waveassist, "_call_llm_claude_cli", fake_cli)
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli")

    waveassist.call_llm("anthropic/claude-sonnet-4.6", "hi", _Dummy)
    assert calls["use_setup_token"] is False


def test_claude_cli_token_injects_token_and_isolates_config(store, monkeypatch):
    captured = {}
    store[CLAUDE_SETUP_TOKEN_STORED_DATA_KEY] = "sk-ant-oat01-TESTTOKEN"
    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-removed")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "should-be-removed")
    monkeypatch.setattr(waveassist.subprocess, "run", _fake_claude_run(captured))

    result = waveassist._call_llm_claude_cli(
        "anthropic/claude-sonnet-4.6", "hi", _Dummy, use_setup_token=True
    )
    assert isinstance(result, _Dummy) and result.ok is True

    env = captured["kwargs"]["env"]
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-TESTTOKEN"
    assert env.get("CLAUDE_CONFIG_DIR")  # isolated per-call config home
    # conflicting auth must be scrubbed so the OAuth token wins (subscription, not API billing)
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    # never bare: bare mode ignores CLAUDE_CODE_OAUTH_TOKEN
    assert "--bare" not in captured["cmd"]
    # model still resolved to CLI form
    assert "claude-sonnet-4-6" in captured["cmd"]


def test_claude_cli_token_cleans_up_config_dir(store, monkeypatch):
    captured = {}
    store[CLAUDE_SETUP_TOKEN_STORED_DATA_KEY] = "sk-ant-oat01-X"
    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setattr(waveassist.subprocess, "run", _fake_claude_run(captured))

    waveassist._call_llm_claude_cli(
        "anthropic/claude-sonnet-4.6", "hi", _Dummy, use_setup_token=True
    )
    config_dir = captured["kwargs"]["env"]["CLAUDE_CONFIG_DIR"]
    assert not os.path.exists(config_dir)  # per-call temp dir removed after the run


def test_claude_cli_token_missing_token_raises(store, monkeypatch):
    def boom_run(*a, **k):
        raise AssertionError("subprocess must not run when no setup token is stored")

    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setattr(waveassist.subprocess, "run", boom_run)
    # store has no 'claude_setup_token'
    with pytest.raises(ValueError, match="setup token"):
        waveassist._call_llm_claude_cli(
            "anthropic/claude-sonnet-4.6", "hi", _Dummy, use_setup_token=True
        )


def test_claude_cli_local_mode_does_not_inject_env(store, monkeypatch):
    """use_setup_token False (default) preserves today's behavior: no env override,
    so the subprocess inherits the host's existing `claude login`."""
    captured = {}
    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setattr(waveassist.subprocess, "run", _fake_claude_run(captured))

    waveassist._call_llm_claude_cli("anthropic/claude-sonnet-4.6", "hi", _Dummy)
    assert "env" not in captured["kwargs"]


# --------------- claude_cli_args passthrough (image OCR / extra CLI flags) ---------------


def test_claude_cli_args_appended_and_overrides_max_turns(store, monkeypatch):
    captured = {}
    store[CLAUDE_SETUP_TOKEN_STORED_DATA_KEY] = "sk-ant-oat01-X"
    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setattr(waveassist.subprocess, "run", _fake_claude_run(captured))

    waveassist._call_llm_claude_cli(
        "anthropic/claude-sonnet-4.6", "read it", _Dummy, use_setup_token=True,
        claude_cli_args=["--add-dir", "/tmp/x", "--allowedTools", "Read", "--max-turns", "3"],
    )
    cmd = captured["cmd"]
    assert "--add-dir" in cmd and "/tmp/x" in cmd
    assert "--allowedTools" in cmd and "Read" in cmd
    # caller supplied --max-turns, so the default 1 is NOT added (exactly one, = 3)
    assert cmd.count("--max-turns") == 1
    assert cmd[cmd.index("--max-turns") + 1] == "3"


def test_claude_cli_args_default_keeps_max_turns_1(store, monkeypatch):
    captured = {}
    store[CLAUDE_SETUP_TOKEN_STORED_DATA_KEY] = "sk-ant-oat01-X"
    monkeypatch.delenv("CLAUDE_CLI_MODEL", raising=False)
    monkeypatch.setattr(waveassist.subprocess, "run", _fake_claude_run(captured))

    waveassist._call_llm_claude_cli("anthropic/claude-sonnet-4.6", "hi", _Dummy, use_setup_token=True)
    cmd = captured["cmd"]
    assert cmd.count("--max-turns") == 1
    assert cmd[cmd.index("--max-turns") + 1] == "1"


def test_call_llm_threads_claude_cli_args_env_path(monkeypatch):
    """call_llm forwards claude_cli_args to the claude path (env-override route)."""
    calls = {}

    def fake_cli(model, prompt, response_model, **kwargs):
        calls["claude_cli_args"] = kwargs.get("claude_cli_args")
        return _Dummy(ok=True)

    monkeypatch.setattr(waveassist, "_call_llm_claude_cli", fake_cli)
    monkeypatch.setenv("LLM_PROVIDER", "claude_cli")
    waveassist.call_llm("m", "hi", _Dummy, claude_cli_args=["--add-dir", "/tmp/x"])
    assert calls["claude_cli_args"] == ["--add-dir", "/tmp/x"]


def test_call_llm_threads_claude_cli_args_registry_path(monkeypatch):
    """claude_cli_args also threads through the llm_models registry route."""
    calls = {}

    def fake_cli(model, prompt, response_model, **kwargs):
        calls["claude_cli_args"] = kwargs.get("claude_cli_args")
        return _Dummy(ok=True)

    monkeypatch.setattr(waveassist, "_call_llm_claude_cli", fake_cli)
    monkeypatch.setattr(waveassist, "_resolve_model_entry",
                        lambda m: {"provider": "claude_cli_token", "model": "sonnet", "token": "sk-x"})
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    waveassist.call_llm("sonnet", "hi", _Dummy, claude_cli_args=["--add-dir", "/tmp/x"])
    assert calls["claude_cli_args"] == ["--add-dir", "/tmp/x"]


def test_claude_cli_args_not_leaked_to_hosted_create(azure_routing):
    """As a named param, claude_cli_args must never reach the OpenAI/OpenRouter create()."""
    store, created = azure_routing
    store[AZURE_OPENAI_CONFIG_STORED_DATA_KEY] = {
        "api_key": "k", "endpoint": "https://x.openai.azure.com/",
    }
    waveassist.call_llm("gpt-5.4", "hi", _Dummy, claude_cli_args=["--add-dir", "/tmp/x"])
    _, kw = created[-1].calls[0]
    assert "claude_cli_args" not in kw
