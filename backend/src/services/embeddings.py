from src.auth.credentials import load_api_key, load_model_config
from src.memory.signatures import signature_for


async def configured_signature() -> str:
    """Return the signature for the currently-configured embedding model."""
    config = await load_model_config()
    embedding = config["embedding"]
    return signature_for(embedding["provider"], embedding["model"])


async def get_embedding_function():
    """Return an embedding function for the currently-configured model.

    Raises ValueError if the configured provider requires an API key and none
    is available. Legacy shim — prefer embedding_function_for_signature.
    """
    config = await load_model_config()
    embedding = config["embedding"]
    return await embedding_function_for_signature(
        signature_for(embedding["provider"], embedding["model"]),
        provider=embedding["provider"],
        model=embedding["model"],
    )


async def embedding_function_for_signature(signature: str, *, provider: str, model: str):
    """Build a Chroma embedding function for a given signature.

    The signature must match the provider/model being passed. This lets callers
    instantiate an EF for a non-active signature (e.g., during reindex).
    """
    if provider == "sentence_transformer":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=model)

    api_key = await load_api_key(provider)
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            f"Configure a key in Settings to use '{model}'."
        )

    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    kwargs = {"api_key": api_key, "model_name": model}
    if provider == "openrouter":
        kwargs["api_base"] = "https://openrouter.ai/api/v1"
    return OpenAIEmbeddingFunction(**kwargs)
