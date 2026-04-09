import pytest


@pytest.fixture(autouse=True)
def _disable_langsmith(monkeypatch):
    """Prevent all tests from leaving traces in LangSmith."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
