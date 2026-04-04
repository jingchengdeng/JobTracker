from langchain_core.language_models import BaseChatModel
from src.auth.credentials import load_api_key, load_model_config


def get_chat_model(model_name: str | None = None) -> BaseChatModel:
    """Create a LangChain chat model based on the model name and available credentials."""
    config = load_model_config()
    model = model_name or config["defaultModel"]

    if model.startswith("claude"):
        return _create_anthropic(model)
    elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        return _create_openai(model)
    else:
        return _create_openrouter(model)


def get_classifier_model() -> BaseChatModel:
    """Get the model configured for classification tasks."""
    config = load_model_config()
    return get_chat_model(config["classifierModel"])


def _create_openai(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    api_key = load_api_key("openai")
    if not api_key:
        raise ValueError("No OpenAI API key found. Add one in Settings or .env")
    return ChatOpenAI(model=model, api_key=api_key)


def _create_anthropic(model: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    api_key = load_api_key("anthropic")
    if not api_key:
        raise ValueError("No Anthropic API key found. Add one in Settings or .env")
    return ChatAnthropic(model=model, api_key=api_key)


def _create_openrouter(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    api_key = load_api_key("openrouter")
    if not api_key:
        raise ValueError("No OpenRouter API key found. Add one in Settings or .env")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
