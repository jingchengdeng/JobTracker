import json
import os
from pathlib import Path
from typing import Optional


def get_auth_file_path() -> str:
    return os.environ.get(
        "AUTH_PROFILES_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data" / "auth-profiles.json"),
    )


def get_model_config_path() -> str:
    return os.environ.get(
        "MODEL_CONFIG_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data" / "model-config.json"),
    )


def load_api_key(provider: str) -> Optional[str]:
    """Load API key for a provider. Checks auth-profiles.json first, then .env."""
    auth_path = get_auth_file_path()
    if os.path.exists(auth_path):
        with open(auth_path) as f:
            store = json.load(f)
        profile_id = f"{provider}:default"
        profile = store.get("profiles", {}).get(profile_id)
        if profile:
            if profile["type"] == "api_key":
                return profile["key"]
            elif profile["type"] == "oauth":
                return profile.get("access")

    # Fall back to environment variables
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        return os.environ.get(env_var)

    return None


def load_model_config() -> dict:
    """Load model configuration."""
    config_path = get_model_config_path()
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return {
        "defaultModel": "gpt-4o",
        "classifierModel": "gpt-4o-mini",
        "embeddingModel": "text-embedding-3-small",
    }
