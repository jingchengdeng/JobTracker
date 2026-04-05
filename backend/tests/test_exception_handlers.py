from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.exception_handlers import register_exception_handlers


def test_chroma_conflict_returns_structured_409():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise ValueError(
            "An embedding function already exists in the collection configuration, "
            "and a new one is provided. Embedding function conflict: "
            "new: openai vs persisted: sentence_transformer"
        )

    client = TestClient(app)
    resp = client.get("/boom")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "embedding_mismatch"
    assert body["new"] == "openai"
    assert body["persisted"] == "sentence_transformer"


def test_unrelated_value_error_is_not_caught():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/other")
    async def other():
        raise ValueError("some other problem")

    client = TestClient(app)
    # Starlette's TestClient raises server-side exceptions by default unless
    # configured otherwise. Use raise_server_exceptions=False so we can assert
    # the 500 response.
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/other")
    assert resp.status_code == 500
