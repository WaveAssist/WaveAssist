"""
Tests for LLM provider routing in call_llm:
  - provider resolution (env > server > default)
  - hosted client construction for openrouter / azure
  - azure config validation and max_tokens -> max_completion_tokens rename
  - claude_cli routing (local CLI, no OpenAI client)
"""
import sys
import os
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

    result = waveassist.call_llm("gpt-5.4-pro", "hello", _Dummy, max_tokens=500)

    assert isinstance(result, _Dummy) and result.ok is True
    client = created[-1]
    assert [c[0] for c in client.calls] == ["responses.parse"]
    _, kw = client.calls[0]
    assert kw["text_format"] is _Dummy
    # Responses API takes max_output_tokens, never chat-only token args.
    assert kw["max_output_tokens"] == 500
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
