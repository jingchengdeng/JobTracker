import json
from unittest.mock import patch, MagicMock
import pytest


def _make_profile(type_="api_key", provider="openai", key="fake-key", access=None):
    p = {"type": type_, "provider": provider}
    if key:
        p["key"] = key
    if access:
        p["access"] = access
    return p


class TestCreateChatModel:
    """Layer 1: Verify each provider constructs the correct LangChain client."""

    @patch("src.models.provider.load_credential")
    @patch("src.models.provider.ChatOpenAI")
    def test_openai_uses_responses_api(self, mock_chat, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = _make_profile()
        _create_chat_model("openai", "gpt-5.4")
        mock_chat.assert_called_once_with(
            model="gpt-5.4",
            api_key="fake-key",
            use_responses_api=True,
        )

    @patch("src.models.provider.load_credential")
    @patch("src.models.provider.ChatOpenAI")
    def test_openai_codex_sends_attribution_headers(self, mock_chat, mock_cred):
        import base64, json
        from src.models.provider import _create_chat_model

        claims = {"https://api.openai.com/auth": {"chatgpt_account_id": "acc_xyz"}}
        body = (
            base64.urlsafe_b64encode(json.dumps(claims).encode())
            .rstrip(b"=")
            .decode()
        )
        token = f"hdr.{body}.sig"
        mock_cred.return_value = _make_profile(
            type_="oauth", provider="openai-codex", key=None, access=token
        )
        _create_chat_model("openai-codex", "gpt-5.4")

        assert mock_chat.call_count == 1
        kwargs = mock_chat.call_args.kwargs
        assert kwargs["model"] == "gpt-5.4"
        assert kwargs["api_key"] == token
        assert kwargs["base_url"] == "https://chatgpt.com/backend-api/codex"
        assert kwargs["use_responses_api"] is True
        assert kwargs["streaming"] is True
        assert kwargs["store"] is False
        assert kwargs["model_kwargs"]["instructions"]
        assert "http_client" in kwargs
        headers = kwargs["default_headers"]
        assert headers["chatgpt-account-id"] == "acc_xyz"
        assert headers["originator"] == "jobtracker"
        assert headers["OpenAI-Beta"] == "responses=experimental"
        assert headers["User-Agent"].startswith("jobtracker/")
        assert headers["version"] == "0.1.0"

    @patch("src.models.provider.load_credential")
    @patch("src.models.provider.ChatAnthropic")
    def test_anthropic_uses_anthropic_client(self, mock_chat, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = _make_profile(provider="anthropic")
        _create_chat_model("anthropic", "claude-sonnet-4-6")
        mock_chat.assert_called_once_with(
            model="claude-sonnet-4-6",
            api_key="fake-key",
        )

    @patch("src.models.provider.load_credential")
    @patch("src.models.provider.ChatAnthropic")
    def test_kimi_uses_anthropic_client_with_base_url(self, mock_chat, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = _make_profile(provider="kimi")
        _create_chat_model("kimi", "kimi-k2.5")
        mock_chat.assert_called_once_with(
            model="kimi-k2.5",
            api_key="fake-key",
            base_url="https://api.kimi.com/coding/",
        )

    @patch("src.models.provider.load_credential")
    @patch("src.models.provider.ChatOpenAI")
    def test_openrouter_uses_completions_no_responses_flag(self, mock_chat, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = _make_profile(provider="openrouter")
        _create_chat_model("openrouter", "deepseek/deepseek-v3")
        mock_chat.assert_called_once_with(
            model="deepseek/deepseek-v3",
            api_key="fake-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @patch("src.models.provider.load_credential")
    def test_no_credentials_raises(self, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = None
        with pytest.raises(ValueError, match="No credentials"):
            _create_chat_model("openai", "gpt-5.4")

    def test_unknown_provider_raises(self):
        from src.models.provider import _create_chat_model

        with pytest.raises(ValueError, match="Unknown provider"):
            _create_chat_model("nonexistent", "some-model")


class TestCodexRequestRewrite:
    """Verify the httpx hook that adapts request bodies for chatgpt.com/backend-api/codex."""

    def _make_request(self, body: dict, path: str = "/codex/responses") -> "httpx.Request":
        import httpx
        return httpx.Request(
            "POST",
            f"https://chatgpt.com/backend-api{path}",
            content=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
        )

    def _read_body(self, request) -> dict:
        chunks = b"".join(request.stream)
        return json.loads(chunks)

    def test_moves_system_message_into_instructions(self):
        from src.models.provider import _codex_rewrite_request

        req = self._make_request({
            "model": "gpt-5.4",
            "instructions": "You are a helpful assistant.",
            "input": [
                {"role": "system", "content": "Be terse.", "type": "message"},
                {"role": "user", "content": "hi", "type": "message"},
            ],
        })
        _codex_rewrite_request(req)
        body = self._read_body(req)
        assert body["instructions"] == "You are a helpful assistant.\n\nBe terse."
        assert body["input"] == [
            {"role": "user", "content": "hi", "type": "message"},
        ]
        assert int(req.headers["content-length"]) == len(json.dumps(body).encode())

    def test_handles_list_content_parts(self):
        from src.models.provider import _codex_rewrite_request

        req = self._make_request({
            "instructions": "base",
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": "A"}, {"type": "input_text", "text": "B"}],
                    "type": "message",
                },
                {"role": "user", "content": "q", "type": "message"},
            ],
        })
        _codex_rewrite_request(req)
        body = self._read_body(req)
        assert body["instructions"] == "base\n\nA\n\nB"
        assert len(body["input"]) == 1

    def test_noop_when_no_system_messages(self):
        from src.models.provider import _codex_rewrite_request

        original_body = {
            "instructions": "keep me",
            "input": [{"role": "user", "content": "hi", "type": "message"}],
        }
        req = self._make_request(original_body)
        original_bytes = b"".join(req.stream)
        _codex_rewrite_request(req)
        assert b"".join(req.stream) == original_bytes

    def test_skips_non_responses_paths(self):
        from src.models.provider import _codex_rewrite_request

        req = self._make_request({
            "input": [{"role": "system", "content": "x", "type": "message"}],
        }, path="/codex/other")
        original_bytes = b"".join(req.stream)
        _codex_rewrite_request(req)
        assert b"".join(req.stream) == original_bytes


class TestGetChatModelFallback:
    """Layer 2: Verify fallback logic."""

    @patch("src.models.provider.load_model_config")
    @patch("src.models.provider._create_chat_model")
    def test_fallback_on_primary_failure(self, mock_create, mock_config):
        from src.models.provider import get_chat_model

        mock_config.return_value = {
            "default": {
                "provider": "kimi",
                "model": "kimi-k2.5",
                "fallback": {"provider": "openai-codex", "model": "gpt-5.4"},
            }
        }
        mock_create.side_effect = [ValueError("no creds"), MagicMock()]
        get_chat_model("default")
        assert mock_create.call_count == 2
        mock_create.assert_called_with("openai-codex", "gpt-5.4")

    @patch("src.models.provider.load_model_config")
    @patch("src.models.provider._create_chat_model")
    def test_no_fallback_propagates_error(self, mock_create, mock_config):
        from src.models.provider import get_chat_model

        mock_config.return_value = {
            "default": {
                "provider": "kimi",
                "model": "kimi-k2.5",
                "fallback": None,
            }
        }
        mock_create.side_effect = ValueError("no creds")
        with pytest.raises(ValueError, match="no creds"):
            get_chat_model("default")

    @patch("src.models.provider.load_model_config")
    @patch("src.models.provider._create_chat_model")
    def test_primary_success_no_fallback_attempt(self, mock_create, mock_config):
        from src.models.provider import get_chat_model

        mock_config.return_value = {
            "default": {
                "provider": "openai",
                "model": "gpt-5.4",
                "fallback": {"provider": "openai-codex", "model": "gpt-5.4"},
            }
        }
        mock_create.return_value = MagicMock()
        get_chat_model("default")
        assert mock_create.call_count == 1


class TestMigrateModelConfig:
    """Layer 3: Verify old format auto-migrates."""

    def test_old_format_migrates(self):
        from src.auth.credentials import _migrate_model_config

        old = {
            "defaultModel": "gpt-4o",
            "classifierModel": "gpt-4o-mini",
            "embeddingModel": "text-embedding-3-small",
        }
        result = _migrate_model_config(old)
        assert result["default"]["provider"] == "openai"
        assert result["default"]["model"] == "gpt-4o"
        assert result["default"]["fallback"] is None
        assert result["classifier"]["provider"] == "openai"
        assert result["classifier"]["model"] == "gpt-4o-mini"
        assert result["embedding"]["model"] == "text-embedding-3-small"

    def test_new_format_passes_through(self):
        from src.auth.credentials import _migrate_model_config

        new = {
            "default": {"provider": "kimi", "model": "kimi-k2.5", "fallback": None},
            "classifier": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small", "fallback": None},
        }
        result = _migrate_model_config(new)
        assert result == new


class TestExtractChatgptAccountId:
    """Parses chatgpt_account_id from an OpenAI OAuth JWT."""

    def _make_jwt(self, payload: dict) -> str:
        import base64, json
        header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
        body = (
            base64.urlsafe_b64encode(json.dumps(payload).encode())
            .rstrip(b"=")
            .decode()
        )
        return f"{header}.{body}.sig"

    def test_extracts_account_id_from_auth_claim(self):
        from src.models.provider import _extract_chatgpt_account_id

        token = self._make_jwt(
            {"https://api.openai.com/auth": {"chatgpt_account_id": "acc_123"}}
        )
        assert _extract_chatgpt_account_id(token) == "acc_123"

    def test_handles_unpadded_base64(self):
        from src.models.provider import _extract_chatgpt_account_id

        # Long account id forces a payload length that needs base64 padding.
        token = self._make_jwt(
            {"https://api.openai.com/auth": {"chatgpt_account_id": "a" * 37}}
        )
        assert _extract_chatgpt_account_id(token) == "a" * 37

    def test_missing_claim_raises(self):
        import pytest
        from src.models.provider import _extract_chatgpt_account_id

        token = self._make_jwt({"some": "other"})
        with pytest.raises(ValueError, match="chatgpt_account_id"):
            _extract_chatgpt_account_id(token)

    def test_malformed_token_raises(self):
        import pytest
        from src.models.provider import _extract_chatgpt_account_id

        with pytest.raises(ValueError, match="chatgpt_account_id"):
            _extract_chatgpt_account_id("not.a.jwt")


@pytest.mark.live
class TestLiveProviderSmoke:
    """Layer 4: Live smoke tests — only run with credentials present."""

    def test_openai_live(self):
        from src.auth.credentials import load_api_key
        from src.models.provider import _create_chat_model

        key = load_api_key("openai")
        if not key:
            pytest.skip("No openai credentials configured")
        model = _create_chat_model("openai", "gpt-4o-mini")
        result = model.invoke("Reply with the word hello")
        assert result.content

    def test_openai_codex_live(self):
        from src.auth.credentials import load_api_key
        from src.models.provider import _create_chat_model

        key = load_api_key("openai-codex")
        if not key:
            pytest.skip("No openai-codex credentials configured")
        model = _create_chat_model("openai-codex", "gpt-5.4")
        result = model.invoke("Reply with the word hello")
        assert result.content, "codex returned empty content"
        text = result.content if isinstance(result.content, str) else str(result.content)
        assert "<html" not in text.lower(), (
            "codex returned an HTML page instead of a model response: " + text[:200]
        )

    def test_anthropic_live(self):
        from src.auth.credentials import load_api_key
        from src.models.provider import _create_chat_model

        key = load_api_key("anthropic")
        if not key:
            pytest.skip("No anthropic credentials configured")
        model = _create_chat_model("anthropic", "claude-haiku-4-5")
        result = model.invoke("Reply with the word hello")
        assert result.content

    def test_kimi_live(self):
        from src.auth.credentials import load_api_key
        from src.models.provider import _create_chat_model

        key = load_api_key("kimi")
        if not key:
            pytest.skip("No kimi credentials configured")
        model = _create_chat_model("kimi", "kimi-k2")
        result = model.invoke("Reply with the word hello")
        assert result.content
