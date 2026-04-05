import pytest
from unittest.mock import patch

from src.services.embeddings import (
    embedding_function_for_signature,
    configured_signature,
)


def test_configured_signature_from_model_config():
    fake_config = {
        "embedding": {"provider": "openai", "model": "text-embedding-3-small"}
    }
    with patch("src.services.embeddings.load_model_config", return_value=fake_config):
        assert configured_signature() == "openai__text_embedding_3_small"


def test_embedding_function_for_openai_signature_uses_key():
    with patch("src.services.embeddings.load_api_key", return_value="sk-test"):
        ef = embedding_function_for_signature(
            "openai__text_embedding_3_small",
            provider="openai",
            model="text-embedding-3-small",
        )
    assert ef is not None


def test_embedding_function_for_sentence_transformer_no_key_needed():
    with patch("src.services.embeddings.load_api_key", return_value=None):
        ef = embedding_function_for_signature(
            "sentence_transformer__all_minilm_l6_v2",
            provider="sentence_transformer",
            model="all-MiniLM-L6-v2",
        )
    assert ef is not None


def test_embedding_function_for_openai_signature_without_key_raises():
    with patch("src.services.embeddings.load_api_key", return_value=None):
        with pytest.raises(ValueError, match="API key"):
            embedding_function_for_signature(
                "openai__text_embedding_3_small",
                provider="openai",
                model="text-embedding-3-small",
            )
