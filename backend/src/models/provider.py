import base64
import json

import httpx
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


_APP_ORIGINATOR = "jobtracker"
_APP_VERSION = "0.1.0"


def _codex_rewrite_request(request: httpx.Request) -> None:
    """Rewrite outgoing request body to match chatgpt.com/backend-api/codex.

    The Codex endpoint rejects system-role messages inside `input` and
    requires them to live in the top-level `instructions` field instead.
    LangChain's ChatOpenAI always puts SystemMessage into input, so we
    rewrite the body on the way out: pull system content out, merge it
    into instructions, and drop the system messages from input.
    """
    if not request.url.path.endswith("/responses"):
        return
    try:
        body = json.loads(request.content)
    except (ValueError, TypeError):
        return
    input_items = body.get("input")
    if not isinstance(input_items, list):
        return
    system_texts: list[str] = []
    kept: list[dict] = []
    for item in input_items:
        if isinstance(item, dict) and item.get("role") == "system":
            content = item.get("content")
            if isinstance(content, str):
                system_texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str):
                            system_texts.append(text)
        else:
            kept.append(item)
    if not system_texts:
        return
    existing = body.get("instructions") or ""
    merged = "\n\n".join([existing, *system_texts]).strip()
    body["instructions"] = merged
    body["input"] = kept
    new_content = json.dumps(body).encode()
    request.stream = httpx.ByteStream(new_content)
    request.headers["content-length"] = str(len(new_content))


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
        if provider["api"] == "codex-responses":
            account_id = _extract_chatgpt_account_id(api_key)
            kwargs["streaming"] = True
            kwargs["default_headers"] = {
                "chatgpt-account-id": account_id,
                "originator": _APP_ORIGINATOR,
                "version": _APP_VERSION,
                "User-Agent": f"{_APP_ORIGINATOR}/{_APP_VERSION}",
                "OpenAI-Beta": "responses=experimental",
            }
            # chatgpt.com/backend-api/codex requires store=false and a
            # non-empty top-level `instructions` field, and rejects
            # system-role messages inside `input`. We seed a default
            # instructions string; the httpx hook below moves any system
            # messages LangChain put into `input` up into `instructions`.
            kwargs["model_kwargs"] = {"instructions": "You are a helpful assistant."}
            kwargs["store"] = False
            kwargs["http_client"] = httpx.Client(
                event_hooks={"request": [_codex_rewrite_request]},
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
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
