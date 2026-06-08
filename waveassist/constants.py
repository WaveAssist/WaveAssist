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
