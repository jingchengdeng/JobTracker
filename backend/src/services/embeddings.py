from src.auth.credentials import load_api_key, load_model_config


def get_embedding_function():
    """Return an embedding function. Uses OpenAI API if available, falls back to local model."""
    config = load_model_config()
    api_key = load_api_key("openai")

    if api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=config.get("embeddingModel", "text-embedding-3-small"),
        )

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
