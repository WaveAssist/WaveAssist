# Azure OpenAI as a selectable provider for `call_llm`

**Date:** 2026-06-08
**Status:** Approved design, pending implementation
**Component:** `waveassist/__init__.py` (`call_llm`), `waveassist/constants.py`

## Goal

Let `call_llm` route to multiple backends, selected per-project via
server-stored config:

- **OpenRouter** (default, current behavior) — hosted, `open_router_key`.
- **Azure OpenAI** — hosted, `azure_openai_config`.
- **Claude CLI** ("claude local") — local dev path using the on-machine
  `claude` binary / Claude Max subscription, no key. Already implemented as
  `_call_llm_claude_cli`; this design promotes it from an env-only hook to a
  first-class `llm_provider` value.

OpenRouter remains the default; existing projects and call sites are unaffected.

## Key finding: no `AzureOpenAI` client needed

Azure exposes an OpenAI-compatible endpoint at
`https://<resource>.openai.azure.com/openai/v1/`. The standard `openai.OpenAI`
client works against it directly — same as OpenRouter, just a different
`base_url` + key. Verified against the `mom` resource for deployments `gpt-4.1`
and `gpt-5.4`, including `response_format={"type":"json_object"}`.

Therefore the Azure path reuses the **entire** existing `call_llm` body
(client type, retry loop, JSON parsing). The only thing that changes per
provider is the `(api_key, base_url)` pair.

## Provider selection

Resolution precedence (first non-empty wins):

1. `os.environ["LLM_PROVIDER"]` — dev/local override, preserves the existing
   `LLM_PROVIDER=claude_cli` hook.
2. `fetch_data(LLM_PROVIDER_STORED_DATA_KEY)` — server-stored per-project value.
3. Default `"openrouter"`.

| Resolved value  | Path                                   | Needs                  |
|-----------------|----------------------------------------|------------------------|
| `"openrouter"`  | `OpenAI` + `OPENROUTER_URL` (current)   | `open_router_key`      |
| `"azure"`       | `OpenAI` + `/openai/v1/`                 | `azure_openai_config`  |
| `"claude_cli"`  | local `claude` CLI subprocess           | local `claude` binary  |
| unset / unknown | falls back to `"openrouter"`            | —                      |

Because unset defaults to OpenRouter, no existing project changes behavior. The
env override keeps `LLM_PROVIDER=claude_cli` working for local development
exactly as today.

`claude_cli` is a **local/dev** provider: it shells out to the `claude` binary
and uses the machine's Claude Max subscription. It is not meaningful in a hosted
server run where that binary/subscription is absent.

## Configuration (all server-stored)

| Stored-data key        | Type | Shape / example                                                        |
|------------------------|------|------------------------------------------------------------------------|
| `llm_provider`         | str  | `"azure"`                                                              |
| `azure_openai_config`  | dict | `{"api_key": "...", "endpoint": "https://mom.openai.azure.com/"}`      |
| `open_router_key`      | str  | *(existing, unchanged)*                                                |

`base_url` for Azure is derived: `endpoint.rstrip("/") + "/openai/v1/"`.
No `api-version` is required by the `/openai/v1/` endpoint.

### Model = deployment name

When provider is `azure`, the `model` argument passed to `call_llm` is used
directly as the Azure **deployment** name (e.g. `call_llm(model="gpt-5.4", ...)`).
No translation layer. (A future optional `deployments` map inside
`azure_openai_config` could add aliasing, but is out of scope — YAGNI.)

## Code structure (`waveassist/__init__.py`)

Add a provider resolver and an HTTP-client resolver; keep the existing
`call_llm` body intact. The Claude CLI path routes via an early return because
it does not use an `OpenAI` client.

```python
def _resolve_llm_provider():
    """Env override (dev) > server config > default openrouter."""
    provider = (os.environ.get("LLM_PROVIDER")
                or fetch_data(LLM_PROVIDER_STORED_DATA_KEY)
                or PROVIDER_OPENROUTER)
    return str(provider).strip().lower()
```

In `call_llm`, replace the current `LLM_PROVIDER=claude_cli` env check
(lines ~643–645) and the inline client construction (lines ~652–663) with:

```python
provider = _resolve_llm_provider()

if provider == PROVIDER_CLAUDE_CLI:
    return _call_llm_claude_cli(model, prompt, response_model, **kwargs)

# init guard (unchanged) ...
client, kwargs = _resolve_llm_client(provider, kwargs)
```

The HTTP-client resolver (azure | openrouter only):

```python
def _resolve_llm_client(provider, kwargs):
    """Return (OpenAI client, kwargs) for hosted providers.
    Defaults to OpenRouter. Adjusts kwargs for provider quirks."""
    if provider == PROVIDER_AZURE:
        config = fetch_data(AZURE_OPENAI_CONFIG_STORED_DATA_KEY)
        # fetch_data may wrap scalars in a list; unwrap dict if needed
        if isinstance(config, list):
            config = config[0] if config else None
        if not config or not config.get("api_key") or not config.get("endpoint"):
            raise ValueError(
                "Azure OpenAI config not found or incomplete. Store it with "
                "waveassist.store_data('azure_openai_config', "
                "{'api_key': '...', 'endpoint': 'https://<resource>.openai.azure.com/'})"
            )
        base_url = config["endpoint"].rstrip("/") + "/openai/v1/"
        client = OpenAI(api_key=config["api_key"], base_url=base_url)
        # Azure newer models require max_completion_tokens, not max_tokens
        if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        return client, kwargs

    # default: OpenRouter (existing behavior)
    api_key = fetch_data(OPENROUTER_API_STORED_DATA_KEY)
    if not api_key:
        raise ValueError(
            "OpenRouter API key not found. Please store it using "
            "waveassist.store_data('open_router_key', 'your_api_key')"
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_URL), kwargs
```

Everything after — `create_json_prompt`, `response_format` handling, the
two-attempt transport/format retry loop, `parse_json_response` — is unchanged.
Both hosted providers use the same `OpenAI` client, so the same exception types
(`APIError`, `APIConnectionError`, `RateLimitError`, `OpenAITimeout`) apply. The
`claude_cli` provider returns earlier and keeps its own error handling.

## `constants.py` additions

```python
LLM_PROVIDER_STORED_DATA_KEY = "llm_provider"
AZURE_OPENAI_CONFIG_STORED_DATA_KEY = "azure_openai_config"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_AZURE = "azure"
PROVIDER_CLAUDE_CLI = "claude_cli"
```

No new import (`AzureOpenAI` not used). No new api-version constant.

## Error handling

- Provider `azure` with missing/incomplete `azure_openai_config` → `ValueError`
  with a `store_data(...)` instruction (mirrors the OpenRouter key error).
- Provider `claude_cli` → existing `_call_llm_claude_cli` error handling
  (`RuntimeError` if the CLI is missing or exits non-zero). Unchanged.
- Unknown `llm_provider` value → treated as OpenRouter (safe default), since the
  resolver only special-cases `"azure"` and `"claude_cli"`.
- Transport/JSON retry behavior is reused unchanged for hosted providers.

## Token-kwarg compatibility

Newer Azure models (`gpt-5.4`) reject `max_tokens` and require
`max_completion_tokens`. The Azure branch auto-renames `max_tokens` →
`max_completion_tokens` (only if the latter isn't already set) so existing
call sites work unchanged on Azure.

## Usage example

```python
import waveassist
waveassist.init(...)

# one-time per project (typically done server-side / by an admin):
waveassist.store_data("azure_openai_config", {
    "api_key": "<azure-key>",
    "endpoint": "https://mom.openai.azure.com/",
})
waveassist.store_data("llm_provider", "azure")

# unchanged call site — model is the Azure deployment name:
result = waveassist.call_llm(
    model="gpt-5.4",
    prompt="Extract user info: John Doe, 30",
    response_model=UserInfo,
    max_completion_tokens=2000,
)
```

Claude local (dev) — either set the env var (existing hook) or store the
provider:

```python
# env hook (unchanged):  LLM_PROVIDER=claude_cli
# or via server config:
waveassist.store_data("llm_provider", "claude_cli")
```

## Testing

Following the monkeypatch style in `tests/test_llm_call.py` (patching
`waveassist.fetch_data`):

1. **Default provider** — no `llm_provider` stored → resolver builds OpenRouter
   client with `OPENROUTER_URL`.
2. **Azure provider** — `llm_provider="azure"` + valid config → resolver builds
   `OpenAI` with `base_url == "https://mom.openai.azure.com/openai/v1/"` and the
   config api_key.
3. **Missing Azure config** — `llm_provider="azure"` with no/partial config →
   `ValueError`.
4. **Token rename** — Azure path with `max_tokens` in kwargs → becomes
   `max_completion_tokens`; not overridden if caller already set it.
5. **Claude CLI routing** — `llm_provider="claude_cli"` (or env
   `LLM_PROVIDER=claude_cli`) → `call_llm` returns via `_call_llm_claude_cli`
   without constructing an `OpenAI` client (assert the CLI helper is invoked).
6. **Env precedence** — env `LLM_PROVIDER` overrides the server-stored value.
7. **Regression** — existing OpenRouter tests still pass unchanged.

Resolver tests mock the client constructor (no live network); an optional
integration test (live Azure call) is gated behind an env-provided key like the
existing `OPENROUTER_API_KEY` pattern.

## Out of scope (YAGNI)

- Deployment-name aliasing / `deployments` map.
- Per-call `provider=` override and `azure/<model>` prefix routing.
- Configurable `api-version` (the v1 endpoint doesn't need it).
- Azure AD / token-based auth (api-key only).
