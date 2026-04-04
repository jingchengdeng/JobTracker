from langchain_core.language_models import BaseChatModel
from src.auth.credentials import load_credential, load_model_config


def get_chat_model(model_name: str | None = None) -> BaseChatModel:
    config = load_model_config()
    model = model_name or config["defaultModel"]

    if model.startswith("claude"):
        return _create_anthropic(model)
    elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        return _create_openai(model)
    else:
        return _create_openrouter(model)


def get_classifier_model() -> BaseChatModel:
    config = load_model_config()
    return get_chat_model(config["classifierModel"])


def _create_openai(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    profile = load_credential("openai")
    if not profile:
        profile = load_credential("openai-codex")
    if not profile:
        raise ValueError("No OpenAI credentials found. Add one in Settings or .env")

    if profile.get("type") == "oauth" and profile.get("provider") == "openai-codex":
        return ChatOpenAI(
            model=model,
            api_key=profile["access"],
            base_url="https://chatgpt.com/backend-api",
        )
    return ChatOpenAI(model=model, api_key=profile["key"])


def _create_anthropic(model: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    profile = load_credential("anthropic")
    if not profile:
        raise ValueError("No Anthropic API key found. Add one in Settings or .env")
    return ChatAnthropic(model=model, api_key=profile["key"])


def _create_openrouter(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    profile = load_credential("openrouter")
    if not profile:
        raise ValueError("No OpenRouter API key found. Add one in Settings or .env")
    return ChatOpenAI(
        model=model,
        api_key=profile["key"],
        base_url="https://openrouter.ai/api/v1",
    )
