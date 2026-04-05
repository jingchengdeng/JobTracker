import base64
import json

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from src.auth.credentials import load_credential, load_model_config
from src.models.registry import get_provider


def _extract_chatgpt_account_id(jwt_token: str) -> str:
    """Parse chatgpt_account_id from the payload of an OpenAI OAuth JWT.

    The token is a standard three-segment JWT. OpenAI stashes the account id
    under a custom claim at "https://api.openai.com/auth". We don't verify
    the signature - we only read public claim data that we just got from the
    OAuth flow.
    """
    try:
        payload_b64 = jwt_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        account_id = payload["https://api.openai.com/auth"]["chatgpt_account_id"]
    except (IndexError, KeyError, ValueError, TypeError) as exc:
        raise ValueError(
            "Could not read chatgpt_account_id from OAuth token"
        ) from exc
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("Could not read chatgpt_account_id from OAuth token")
    return account_id


def _create_chat_model(provider_id: str, model: str) -> BaseChatModel:
    provider = get_provider(provider_id)
    profile = load_credential(provider_id)
    if not profile:
        hint = "Connect via Settings > Auth" if provider["auth"] == "oauth" else "Add one in Settings or .env"
        raise ValueError(
            f"No credentials for {provider['label']}. {hint}"
        )

    api_key = (
        profile.get("access") if profile["type"] == "oauth" else profile.get("key")
    )

    if provider["client"] == "openai":
        kwargs: dict = {"model": model, "api_key": api_key}
        if provider["baseUrl"]:
            kwargs["base_url"] = provider["baseUrl"]
        if provider["api"] in ("responses", "codex-responses"):
            kwargs["use_responses_api"] = True
        return ChatOpenAI(**kwargs)

    if provider["client"] == "anthropic":
        kwargs = {"model": model, "api_key": api_key}
        if provider["baseUrl"]:
            kwargs["base_url"] = provider["baseUrl"]
        return ChatAnthropic(**kwargs)

    raise ValueError(f"Unknown client type: {provider['client']}")


def get_chat_model(role: str = "default") -> BaseChatModel:
    config = load_model_config()
    role_config = config[role]
    try:
        return _create_chat_model(role_config["provider"], role_config["model"])
    except Exception:
        fallback = role_config.get("fallback")
        if fallback:
            return _create_chat_model(fallback["provider"], fallback["model"])
        raise


def get_classifier_model() -> BaseChatModel:
    return get_chat_model("classifier")
