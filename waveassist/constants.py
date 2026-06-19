import os

API_BASE_URL = os.getenv("WAVEASSIST_API_BASE_URL", "https://api.waveassist.io")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
DASHBOARD_URL = "https://app.waveassist.io"
OPENROUTER_API_STORED_DATA_KEY = "open_router_key"
UNSUPPORTED_JSON_MODELS_ARRAY = ["perplexity", "grok"]

# LLM provider selection (server-stored per-project setting)
LLM_PROVIDER_STORED_DATA_KEY = "llm_provider"
AZURE_OPENAI_CONFIG_STORED_DATA_KEY = "azure_openai_config"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_AZURE = "azure"
PROVIDER_CLAUDE_CLI = "claude_cli"

# Azure API surface, set via the "api_type" field in azure_openai_config.
# Reasoning / "pro" models (gpt-5.x-pro, o1/o3, ...) are not exposed on
# chat.completions and must use the Responses API.
AZURE_API_TYPE_CHAT = "chat_completions"
AZURE_API_TYPE_RESPONSES = "responses"
