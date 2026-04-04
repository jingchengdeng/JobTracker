import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from filelock import FileLock


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


def _get_lock() -> FileLock:
    return FileLock(get_auth_file_path() + ".lock", timeout=10)


def _read_store() -> dict:
    auth_path = get_auth_file_path()
    if not os.path.exists(auth_path):
        return {"profiles": {}}
    with open(auth_path) as f:
        return json.load(f)


def _refresh_oauth(provider: str) -> None:
    script = Path(__file__).parent.parent.parent.parent / "scripts" / "oauth-refresh.mjs"
    result = subprocess.run(
        ["node", str(script), provider],
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode().strip()
        raise ValueError(f"Token refresh failed for {provider}: {stderr}")


def load_credential(provider: str) -> Optional[dict]:
    """Load full credential profile. Refreshes OAuth tokens if expired."""
    with _get_lock():
        store = _read_store()
        profile = store.get("profiles", {}).get(f"{provider}:default")

    if not profile:
        return _fallback_to_env(provider)

    if profile.get("type") == "oauth":
        expires = profile.get("expires") or 0
        if expires < time.time() * 1000:
            _refresh_oauth(provider)
            with _get_lock():
                store = _read_store()
                profile = store.get("profiles", {}).get(f"{provider}:default")

    return profile


def load_api_key(provider: str) -> Optional[str]:
    """Load API key string for a provider. For backwards compatibility."""
    profile = load_credential(provider)
    if not profile:
        return None
    if profile["type"] == "api_key":
        return profile.get("key")
    elif profile["type"] == "oauth":
        return profile.get("access")
    return None


def _fallback_to_env(provider: str) -> Optional[dict]:
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "kimi": "KIMI_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        value = os.environ.get(env_var)
        if value:
            return {"type": "api_key", "provider": provider, "key": value}
    return None


def load_model_config() -> dict:
    config_path = get_model_config_path()
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return {
        "defaultModel": "gpt-4o",
        "classifierModel": "gpt-4o-mini",
        "embeddingModel": "text-embedding-3-small",
    }
