"""
Tests — test_pipeline.py
Unit tests for Pipeline module (orchestrator.py) and logger.py.
Covers: pipeline state machine, step execution, logger rotation.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
#  Test Logger (2-Session Rotation)
# ---------------------------------------------------------------------------

class TestLogger:
    """Test logger.py — 2-session rotation, JSON format."""

    def test_setup_creates_log_directory(self, tmp_path):
        """setup_logger() creates logs directory."""
        import logger as log_module

        # Reset singleton
        log_module._logger_initialized = False
        log_module._root_logger = None

        log_dir = str(tmp_path / "test_logs")
        result = log_module.setup_logger(log_dir=log_dir, level="INFO")

        assert Path(log_dir).exists()
        assert (Path(log_dir) / "current_run.log.json").exists()

        # Cleanup singleton for other tests
        log_module._logger_initialized = False
        log_module._root_logger = None

    def test_alias_files_created(self, tmp_path):
        """Setup creates aliases current_run and current_errors."""
        import logger as log_module

        log_dir = tmp_path / "alias_test"
        log_module.setup_logger(log_dir=str(log_dir), level="INFO")

        assert (log_dir / "current_run.log.json").exists()
        assert (log_dir / "current_errors.log.json").exists()

        # Cleanup
        log_module._logger_initialized = False
        log_module._root_logger = None

    def test_log_function_decorator(self, tmp_path):
        """@log_function decorator logs input/output/latency."""
        import logger as log_module

        log_module._logger_initialized = False
        log_module._root_logger = None

        log_dir = str(tmp_path / "decorator_test")
        log_module.setup_logger(log_dir=log_dir, level="DEBUG")

        @log_module.log_function("test")
        def add(a, b):
            return a + b

        result = add(1, 2)
        assert result == 3

        # Read log file
        log_file = Path(log_dir) / "current_run.log.json"
        content = log_file.read_text(encoding="utf-8")
        assert len(content) > 0

        # Cleanup
        log_module._logger_initialized = False
        log_module._root_logger = None

    def test_log_function_captures_exception(self, tmp_path):
        """@log_function logs error when function throws exception."""
        import logger as log_module

        log_module._logger_initialized = False
        log_module._root_logger = None

        log_dir = str(tmp_path / "exception_test")
        log_module.setup_logger(log_dir=log_dir, level="DEBUG")

        @log_module.log_function("test")
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        log_file = Path(log_dir) / "current_run.log.json"
        content = log_file.read_text(encoding="utf-8")
        assert "FAIL" in content or "ERROR" in content

        log_module._logger_initialized = False
        log_module._root_logger = None

    def test_get_logger_returns_child(self):
        """get_logger('module') returns child logger."""
        import logger as log_module
        child = log_module.get_logger("test_module")
        assert child.name == "sports_assistant.test_module"

    def test_truncate_long_string(self):
        """_truncate cuts string > max_len."""
        import logger as log_module
        long_str = "x" * 1000
        result = log_module._truncate(long_str, max_len=100)
        assert len(result) < 200
        assert "truncated" in result

    def test_truncate_short_string(self):
        """_truncate keeps short string as is."""
        import logger as log_module
        assert log_module._truncate("hello") == "hello"

    def test_truncate_none(self):
        """_truncate(None) → None."""
        import logger as log_module
        assert log_module._truncate(None) is None


# ---------------------------------------------------------------------------
#  Test PipelineOrchestrator
# ---------------------------------------------------------------------------

class TestPipelineOrchestrator:
    """Test pipeline orchestrator logic."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.ENV = "DEV"
        settings.LOG_LEVEL = "INFO"
        settings.LOGS_DIR = "logs"
        settings.CRAWL_DAYS_BACK = 7
        settings.GEMINI_API_KEY = "test"
        settings.OPENAI_API_KEY = "test"
        settings.PRIMARY_MODEL = "gemini-2.0-flash"
        settings.FALLBACK_MODEL = "gpt-4o"
        settings.ENABLE_FALLBACK = True
        settings.SUMMARY_MAX_TOKENS = 1024
        settings.API_TIMEOUT_SECONDS = 30
        settings.MAX_ARTICLES_PER_SUMMARY = 50
        settings.KEYWORD_EXTRACTION_COUNT = 15
        settings.TOP_HIGHLIGHTED_NEWS = 10
        return settings

    @patch("logger.setup_logger")
    def test_init_creates_orchestrator(self, mock_setup, mock_settings):
        """Init does not crash."""
        mock_setup.return_value = MagicMock()
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator(mock_settings)
        assert orch.result["status"] == "IDLE"

    @patch("logger.setup_logger")
    def test_result_schema(self, mock_setup, mock_settings):
        """Result dict has correct keys."""
        mock_setup.return_value = MagicMock()
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator(mock_settings)

        assert "status" in orch.result
        assert "started_at" in orch.result
        assert "completed_at" in orch.result
        assert "steps" in orch.result
        assert "errors" in orch.result

    @patch("logger.setup_logger")
    def test_run_invalid_step(self, mock_setup, mock_settings):
        """Running non-existent step → error."""
        mock_setup.return_value = MagicMock()
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator(mock_settings)

        result = orch.run(step="invalid_xyz")
        assert result["status"] == "FAILED"
        assert len(result["errors"]) > 0

    @patch("logger.setup_logger")
    def test_summary_always_printed(self, mock_setup, mock_settings, capsys):
        """Business Rule #5: Summary ALWAYS printed to terminal."""
        mock_setup.return_value = MagicMock()
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator(mock_settings)

        orch.run(step="report")  # Will fail but summary still prints
        captured = capsys.readouterr()
        assert "PIPELINE SUMMARY" in captured.out

    @patch("logger.setup_logger")
    def test_duration_calculated(self, mock_setup, mock_settings):
        """duration_seconds calculated after run."""
        mock_setup.return_value = MagicMock()
        from pipeline.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator(mock_settings)

        result = orch.run(step="report")
        assert result["duration_seconds"] >= 0
        assert result["started_at"] is not None
        assert result["completed_at"] is not None
