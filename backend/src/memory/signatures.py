import re

_SANITIZE_RE = re.compile(r"[^a-z0-9]+")
_COLLECTION_PREFIX = "resume_chunks__"
_CHROMA_MAX_NAME_LEN = 63


def signature_for(provider: str, model: str) -> str:
    """Return canonical signature for an embedding (provider, model) pair.

    Sanitizes both fields to lowercase alphanumeric + underscores and joins
    with a double underscore.
    """
    return f"{_sanitize(provider)}__{_sanitize(model)}"


def collection_name_for(signature: str) -> str:
    """Return the Chroma collection name for a signature.

    Truncates if necessary to stay within Chroma's 63-char limit.
    """
    full = f"{_COLLECTION_PREFIX}{signature}"
    if len(full) <= _CHROMA_MAX_NAME_LEN:
        return full
    return full[:_CHROMA_MAX_NAME_LEN]


def _sanitize(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = _SANITIZE_RE.sub("_", lowered)
    return cleaned.strip("_")
