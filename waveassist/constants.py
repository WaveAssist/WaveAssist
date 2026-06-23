import os

API_BASE_URL = os.getenv("WAVEASSIST_API_BASE_URL", "https://api.waveassist.io")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
DASHBOARD_URL = "https://app.waveassist.io"
OPENROUTER_API_STORED_DATA_KEY = "open_router_key"
UNSUPPORTED_JSON_MODELS_ARRAY = ["perplexity", "grok"]

# LLM provider selection (server-stored per-project setting)
LLM_PROVIDER_STORED_DATA_KEY = "llm_provider"
AZURE_OPENAI_CONFIG_STORED_DATA_KEY = "azure_openai_config"
# Per-model registry: { "<alias>": { provider, model, api_key|token, api_base, api_type, ... } }.
# A model not in the registry falls back to the legacy global provider / OpenRouter default, so the
# common (OpenRouter) path needs no registry at all. Each entry is self-contained, except it MAY point
# at a shared credential via "credential": "<ref>" resolved from LLM_CREDENTIALS_STORED_DATA_KEY.
LLM_MODELS_STORED_DATA_KEY = "llm_models"
LLM_CREDENTIALS_STORED_DATA_KEY = "llm_credentials"
# Setup token (sk-ant-oat01-...) from `claude setup-token`, stored as a Variable.
# Used by the claude_cli_token provider; NOT an API key, draws on a subscription.
CLAUDE_SETUP_TOKEN_STORED_DATA_KEY = "claude_setup_token"
# Run-scoped flag (like display_output) the assistant sets when a cycle did no meaningful work
# (no new PR, a silent scan, a skipped cycle). Absent => the run did work and is shown normally; a
# FAILED run is shown regardless. The dashboard collapses idle runs into a heartbeat count.
RUN_IDLE_STORED_DATA_KEY = "run_idle"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_AZURE = "azure"
# Claude Code CLI (`claude -p`), two auth modes:
#   claude_cli       -> local dev, inherits the host's `claude login`
#   claude_cli_token -> headless fleet, auth via the account's setup token
PROVIDER_CLAUDE_CLI = "claude_cli"
PROVIDER_CLAUDE_CLI_TOKEN = "claude_cli_token"

# Azure API surface, set via the "api_type" field in azure_openai_config.
# Reasoning / "pro" models (gpt-5.x-pro, o1/o3, ...) are not exposed on
# chat.completions and must use the Responses API.
AZURE_API_TYPE_CHAT = "chat_completions"
AZURE_API_TYPE_RESPONSES = "responses"

# Sampling params that reasoning / "pro" models reject with a 400. Callers pass
# these blindly (e.g. temperature=0.5), so the Responses path strips them.
AZURE_RESPONSES_UNSUPPORTED_KWARGS = (
    "temperature",
    "top_p",
    "presence_penalty",
    "frequency_penalty",
    "logprobs",
    "top_logprobs",
    "logit_bias",
)

# On the Responses API, max_output_tokens covers hidden reasoning tokens AND the
# visible answer. Small caller values (sized for chat output only) truncate the
# response -> incomplete -> hard parse failure. Floor an explicit value up to a
# safe minimum; never impose a cap when the caller passed none.
AZURE_RESPONSES_MIN_OUTPUT_TOKENS = 8000
