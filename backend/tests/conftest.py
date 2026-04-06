import pytest


@pytest.fixture(autouse=True)
def _disable_langsmith_for_live_tests(request, monkeypatch):
    """Prevent live smoke tests from leaving traces in LangSmith."""
    if request.node.get_closest_marker("live"):
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
