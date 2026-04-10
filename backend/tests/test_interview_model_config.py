from unittest.mock import patch, MagicMock, AsyncMock
import pytest


class TestInterviewModelConfig:
    def test_default_config_includes_interview(self):
        from src.auth.credentials import DEFAULT_MODEL_CONFIG

        assert "interview" in DEFAULT_MODEL_CONFIG
        assert DEFAULT_MODEL_CONFIG["interview"]["provider"] == "openai"
        assert DEFAULT_MODEL_CONFIG["interview"]["model"] == "gpt-5.4"

    def test_migrate_old_config_backfills_interview(self):
        from src.auth.credentials import _migrate_model_config

        old = {
            "default": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
            "classifier": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small", "fallback": None},
        }
        result = _migrate_model_config(old)
        assert "interview" in result
        assert result["interview"]["provider"] == "openai"

    def test_migrate_new_config_with_interview_passes_through(self):
        from src.auth.credentials import _migrate_model_config

        new = {
            "default": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
            "classifier": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small", "fallback": None},
            "interview": {"provider": "anthropic", "model": "claude-haiku-4-5", "fallback": None},
        }
        result = _migrate_model_config(new)
        assert result["interview"]["provider"] == "anthropic"

    @patch("src.models.provider.load_model_config", new_callable=AsyncMock)
    @patch("src.models.provider._create_chat_model", new_callable=AsyncMock)
    async def test_get_interview_model(self, mock_create, mock_config):
        from src.models.provider import get_interview_model

        mock_config.return_value = {
            "interview": {"provider": "openai", "model": "gpt-5.4-mini", "fallback": None},
        }
        mock_create.return_value = MagicMock()
        await get_interview_model()
        mock_create.assert_called_once_with("openai", "gpt-5.4-mini")


class TestLinkedinModelConfig:
    def test_default_config_includes_linkedin(self):
        from src.auth.credentials import DEFAULT_MODEL_CONFIG
        assert "linkedin" in DEFAULT_MODEL_CONFIG
        assert DEFAULT_MODEL_CONFIG["linkedin"]["provider"] == "openai"
        assert DEFAULT_MODEL_CONFIG["linkedin"]["model"] == "gpt-4o-mini"

    def test_migrate_old_config_backfills_linkedin(self):
        from src.auth.credentials import _migrate_model_config
        old = {
            "default": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
            "classifier": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small", "fallback": None},
            "interview": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
        }
        result = _migrate_model_config(old)
        assert "linkedin" in result
        assert result["linkedin"]["provider"] == "openai"

    def test_migrate_preserves_existing_linkedin(self):
        from src.auth.credentials import _migrate_model_config
        existing = {
            "default": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
            "classifier": {"provider": "openai", "model": "gpt-4o-mini", "fallback": None},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small", "fallback": None},
            "interview": {"provider": "openai", "model": "gpt-5.4", "fallback": None},
            "linkedin": {"provider": "anthropic", "model": "claude-haiku-4-5", "fallback": None},
        }
        result = _migrate_model_config(existing)
        assert result["linkedin"]["provider"] == "anthropic"
