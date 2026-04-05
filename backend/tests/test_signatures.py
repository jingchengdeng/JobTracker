import pytest

from src.memory.signatures import signature_for, collection_name_for


def test_signature_for_openai_model():
    assert signature_for("openai", "text-embedding-3-small") == "openai__text_embedding_3_small"


def test_signature_for_sentence_transformer():
    assert signature_for("sentence_transformer", "all-MiniLM-L6-v2") == "sentence_transformer__all_minilm_l6_v2"


def test_signature_lowercases_model():
    assert signature_for("openai", "Text-Embedding-3-LARGE") == "openai__text_embedding_3_large"


def test_signature_replaces_special_chars():
    assert signature_for("openrouter", "voyage/v3.0") == "openrouter__voyage_v3_0"


def test_signature_is_deterministic():
    a = signature_for("openai", "text-embedding-3-small")
    b = signature_for("openai", "text-embedding-3-small")
    assert a == b


def test_collection_name_prefix():
    sig = signature_for("openai", "text-embedding-3-small")
    assert collection_name_for(sig) == "resume_chunks__openai__text_embedding_3_small"


def test_collection_name_under_63_chars():
    sig = signature_for("openai", "text-embedding-3-small")
    assert len(collection_name_for(sig)) <= 63


def test_collection_name_truncates_very_long_models():
    sig = signature_for("provider", "x" * 100)
    name = collection_name_for(sig)
    assert len(name) <= 63
    assert name.startswith("resume_chunks__provider__")
