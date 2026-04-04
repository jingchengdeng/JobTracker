from src.auth.credentials import load_api_key, load_model_config


def get_embedding_function():
    """Return an embedding function. Uses configured provider if available, falls back to local model."""
    config = load_model_config()
    embedding_config = config["embedding"]
    provider = embedding_config["provider"]
    model = embedding_config["model"]
    api_key = load_api_key(provider)

    if api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        kwargs = {"api_key": api_key, "model_name": model}
        # OpenRouter uses an OpenAI-compatible API at a custom base URL
        if provider == "openrouter":
            kwargs["api_base"] = "https://openrouter.ai/api/v1"
        return OpenAIEmbeddingFunction(**kwargs)

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
