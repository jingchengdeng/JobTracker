PROVIDERS: dict[str, dict] = {
    "openai": {
        "label": "OpenAI",
        "baseUrl": None,
        "client": "openai",
        "api": "responses",
        "auth": "api_key",
        "chatModels": [
            "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.3",
            "gpt-5.2-pro", "gpt-4.1", "gpt-4.1-mini", "gpt-4o",
            "gpt-4o-mini", "o3-mini",
        ],
        "embeddingModels": ["text-embedding-3-small", "text-embedding-3-large"],
    },
    "openai-codex": {
        "label": "OpenAI Codex",
        "baseUrl": "https://chatgpt.com/backend-api",
        "client": "openai",
        "api": "codex-responses",
        "auth": "oauth",
        "chatModels": ["gpt-5.4", "gpt-5.3-codex"],
        "embeddingModels": [],
    },
    "anthropic": {
        "label": "Anthropic",
        "baseUrl": None,
        "client": "anthropic",
        "api": "anthropic-messages",
        "auth": "api_key",
        "chatModels": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
        "embeddingModels": [],
    },
    "kimi": {
        "label": "Kimi",
        "baseUrl": "https://api.kimi.com/coding/",
        "client": "anthropic",
        "api": "anthropic-messages",
        "auth": "api_key",
        "chatModels": ["kimi-k2.5", "kimi-k2", "kimi-k2-thinking"],
        "embeddingModels": [],
    },
    "openrouter": {
        "label": "OpenRouter",
        "baseUrl": "https://openrouter.ai/api/v1",
        "client": "openai",
        "api": "completions",
        "auth": "api_key",
        "chatModels": [],
        "embeddingModels": ["text-embedding-3-small", "text-embedding-3-large"],
    },
}


def get_provider(provider_id: str) -> dict:
    if provider_id not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_id}")
    return PROVIDERS[provider_id]


def get_chat_models(provider_id: str) -> list[str]:
    return get_provider(provider_id)["chatModels"]


def get_embedding_models(provider_id: str) -> list[str]:
    return get_provider(provider_id)["embeddingModels"]


def get_embedding_providers() -> list[str]:
    return [pid for pid, p in PROVIDERS.items() if p["embeddingModels"]]


def get_registry_for_api() -> dict:
    """Return registry data safe for the frontend (no internal fields like client/api)."""
    result = {}
    for pid, p in PROVIDERS.items():
        result[pid] = {
            "label": p["label"],
            "auth": p["auth"],
            "chatModels": p["chatModels"],
            "embeddingModels": p["embeddingModels"],
        }
    return result
