"""
Tests — test_config.py
Unit tests for Config module (config/settings.py).
Covers: validation rules, singleton, edge cases từ SPEC §3.3, §6.
"""

import os
import pytest
from unittest.mock import patch


class TestAppSettings:
    """Test Pydantic AppSettings validation."""

    def _make_env(self, overrides: dict = None) -> dict:
        """Helper: create full env dict, allows overrides."""
        base = {
            "GEMINI_API_KEY": "AIzaSyTestKey1234567890",
            "OPENAI_API_KEY": "sk-test-openai-key-1234567890",
            "ENABLE_FALLBACK": "true",
            "ENV": "DEV",
            "LOG_LEVEL": "INFO",
            "CONCURRENT_REQUESTS": "16",
            "DOWNLOAD_DELAY": "0.5",
            "CRAWL_DAYS_BACK": "7",
        }
        if overrides:
            base.update(overrides)
        return base

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_gemini_key_raises_error(self):
        """SPEC §6 Edge Case #2: empty GEMINI_API_KEY → ValidationError."""
        from pydantic import ValidationError
        env = self._make_env({"GEMINI_API_KEY": ""})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_fallback_requires_openai_key(self):
        """SPEC §6 Edge Case #3: ENABLE_FALLBACK=true + empty OPENAI_API_KEY → Error."""
        from pydantic import ValidationError
        env = self._make_env({
            "ENABLE_FALLBACK": "true",
            "OPENAI_API_KEY": "",
        })
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_fallback_disabled_no_openai_key_ok(self):
        """When ENABLE_FALLBACK=false, empty OPENAI_API_KEY → OK."""
        env = self._make_env({
            "ENABLE_FALLBACK": "false",
            "OPENAI_API_KEY": "",
        })
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.ENABLE_FALLBACK is False
            assert settings.get_fallback_model() is None

    @patch.dict(os.environ, {}, clear=True)
    def test_concurrent_requests_out_of_range(self):
        """SPEC §6 Edge Case #4: CONCURRENT_REQUESTS > 64 → Error."""
        from pydantic import ValidationError
        env = self._make_env({"CONCURRENT_REQUESTS": "100"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_concurrent_requests_negative(self):
        """CONCURRENT_REQUESTS = -1 → Error."""
        from pydantic import ValidationError
        env = self._make_env({"CONCURRENT_REQUESTS": "-1"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_download_delay_out_of_range(self):
        """DOWNLOAD_DELAY > 10 → Error."""
        from pydantic import ValidationError
        env = self._make_env({"DOWNLOAD_DELAY": "15.0"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_crawl_days_back_out_of_range(self):
        """CRAWL_DAYS_BACK > 30 → Error."""
        from pydantic import ValidationError
        env = self._make_env({"CRAWL_DAYS_BACK": "60"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            with pytest.raises(ValidationError):
                AppSettings()

    @patch.dict(os.environ, {}, clear=True)
    def test_valid_config_loads_successfully(self):
        """Normal flow: all fields valid → load OK."""
        env = self._make_env()
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.GEMINI_API_KEY == "AIzaSyTestKey1234567890"
            assert settings.ENV == "DEV"
            assert settings.CONCURRENT_REQUESTS == 16
            assert settings.DOWNLOAD_DELAY == 0.5

    @patch.dict(os.environ, {}, clear=True)
    def test_production_enforces_min_delay(self):
        """SRS Rule #4: ENV=PRODUCTION → DOWNLOAD_DELAY minimum 1.0s."""
        env = self._make_env({"ENV": "PRODUCTION", "DOWNLOAD_DELAY": "0.3"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.DOWNLOAD_DELAY >= 1.0

    @patch.dict(os.environ, {}, clear=True)
    def test_get_active_model(self):
        """SPEC §3.2: get_active_model() returns PRIMARY_MODEL."""
        env = self._make_env({"PRIMARY_MODEL": "gemini-2.0-flash"})
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.get_active_model() == "gemini-2.0-flash"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_fallback_model_enabled(self):
        """SPEC §3.2: fallback enabled → returns FALLBACK_MODEL."""
        env = self._make_env()
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.get_fallback_model() == "gpt-4o"

    @patch.dict(os.environ, {}, clear=True)
    def test_default_storage_paths(self):
        """Config has correct default storage paths."""
        env = self._make_env()
        with patch.dict(os.environ, env, clear=True):
            from config.settings import AppSettings
            settings = AppSettings()
            assert settings.RAW_DATA_DIR == "storage/raw"
            assert settings.PROCESSED_DATA_DIR == "storage/processed"
            assert settings.REPORTS_DIR == "storage/reports"
