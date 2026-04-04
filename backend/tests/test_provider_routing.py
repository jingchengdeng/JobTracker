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
    def test_openai_codex_uses_responses_api_with_base_url(self, mock_chat, mock_cred):
        from src.models.provider import _create_chat_model

        mock_cred.return_value = _make_profile(
            type_="oauth", provider="openai-codex", key=None, access="codex-token"
        )
        _create_chat_model("openai-codex", "gpt-5.4")
        mock_chat.assert_called_once_with(
            model="gpt-5.4",
            api_key="codex-token",
            base_url="https://chatgpt.com/backend-api",
            use_responses_api=True,
        )

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
        assert result.content

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
