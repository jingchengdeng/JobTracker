import json
import os
import subprocess
import time
from contextlib import contextmanager
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


def _lock_dir_path() -> str:
    return get_auth_file_path() + ".lk"


@contextmanager
def _file_lock(retries: int = 15, min_delay: float = 0.05, max_delay: float = 0.5):
    """Cross-language compatible mkdir-based lock.

    Uses the same .lk directory as the Node.js auth-store helpers,
    ensuring Python and Node never write to auth-profiles.json simultaneously.
    """
    lock_dir = _lock_dir_path()
    os.makedirs(os.path.dirname(lock_dir), exist_ok=True)

    for i in range(retries):
        try:
            os.mkdir(lock_dir)
            break
        except FileExistsError:
            # Check for stale lock (older than 30 seconds)
            try:
                st = os.stat(lock_dir)
                if time.time() - st.st_mtime > 30:
                    os.rmdir(lock_dir)
                    continue
            except (FileNotFoundError, OSError):
                continue
            delay = min(min_delay * (2 ** i), max_delay)
            time.sleep(delay)
    else:
        raise TimeoutError("Could not acquire auth file lock after retries")

    try:
        yield
    finally:
        try:
            os.rmdir(lock_dir)
        except OSError:
            pass


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
    with _file_lock():
        store = _read_store()
        profile = store.get("profiles", {}).get(f"{provider}:default")

    if not profile:
        return _fallback_to_env(provider)

    if profile.get("type") == "oauth":
        expires = profile.get("expires") or 0
        if expires < time.time() * 1000:
            _refresh_oauth(provider)
            with _file_lock():
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
