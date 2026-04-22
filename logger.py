"""
Intelligent Sports News Assistant — Deep Logger (2-Session Rotation)

JSON logging system with session-based rotation:
  - current_run.log.json  : Log of the current session
  - previous_run.log.json : Log of the previous session
  
When the application starts:
  1. Delete old previous_run.log.json (if any)
  2. Rename current_run.log.json → previous_run.log.json
  3. Create new current_run.log.json (empty)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional


# Vietnam Timezone (+7)
_VN_TZ = timezone(timedelta(hours=7))

# Fixed log filenames for quick access
LATEST_LOG_NAME = "current_run.log.json"
LATEST_ERRORS_NAME = "current_errors.log.json"


class _JsonFormatter(logging.Formatter):
    """Format each log record into a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(_VN_TZ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Attach extra fields if available (input, output, error, latency_ms)
        for key in ("input", "output", "error", "latency_ms", "step", "details"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def _get_dynamic_log_paths(log_dir_root: Path) -> tuple[Path, Path]:
    """
    Create directory structure: logs/{MM-YYYY}/{DD}/
    Returns (full_log_path, error_log_path)
    """
    now = datetime.now(_VN_TZ)
    month_dir = now.strftime("%m-%Y")
    day_dir = now.strftime("%d")
    time_str = now.strftime("%H%M%S")

    target_dir = log_dir_root / month_dir / day_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    full_path = target_dir / f"run_{time_str}.log.json"
    error_path = target_dir / f"run_{time_str}_errors.log.json"

    return full_path, error_path


def _update_latest_aliases(log_dir_root: Path) -> None:
    """
    Reset alias files in logs/ root for each new session.
    """
    for alias_name in (LATEST_LOG_NAME, LATEST_ERRORS_NAME):
        alias_path = log_dir_root / alias_name
        try:
            if alias_path.exists():
                alias_path.unlink()
            alias_path.touch()
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Singleton Logger Instance
# ---------------------------------------------------------------------------

_logger_initialized = False
_root_logger: Optional[logging.Logger] = None


def setup_logger(log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    """
    Initialize global logger with hierarchical directory structure and separate error logs.

    Args:
        log_dir: Path to the directory containing log files.
        level: Main log level (DEBUG, INFO).

    Returns:
        Configured logging.Logger.
    """
    global _logger_initialized, _root_logger

    if _logger_initialized and _root_logger is not None:
        return _root_logger

    log_root = Path(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)

    # Get log file paths for this session
    full_log_path, error_log_path = _get_dynamic_log_paths(log_root)
    
    # Reset alias files
    _update_latest_aliases(log_root)

    # Create root logger
    logger = logging.getLogger("sports_assistant")
    logger.setLevel(logging.DEBUG) # Root level is set to lowest, filtering happens at handlers
    logger.handlers.clear()

    # 1. Handler: FULL LOG (All information for this session)
    full_handler = logging.FileHandler(filename=str(full_log_path), mode="a", encoding="utf-8")
    full_handler.setFormatter(_JsonFormatter())
    full_handler.setLevel(logging.DEBUG)
    logger.addHandler(full_handler)

    # 2. Handler: ERROR LOG (Only WARNING/ERROR for this session)
    error_handler = logging.FileHandler(filename=str(error_log_path), mode="a", encoding="utf-8")
    error_handler.setFormatter(_JsonFormatter())
    error_handler.setLevel(logging.WARNING)
    logger.addHandler(error_handler)

    # 3. Handler: ALIAS FULL (current_run.log.json)
    alias_full_handler = logging.FileHandler(filename=str(log_root / LATEST_LOG_NAME), mode="w", encoding="utf-8")
    alias_full_handler.setFormatter(_JsonFormatter())
    alias_full_handler.setLevel(logging.DEBUG)
    logger.addHandler(alias_full_handler)

    # 4. Handler: ALIAS ERROR (current_errors.log.json)
    alias_error_handler = logging.FileHandler(filename=str(log_root / LATEST_ERRORS_NAME), mode="w", encoding="utf-8")
    alias_error_handler.setFormatter(_JsonFormatter())
    alias_error_handler.setLevel(logging.WARNING)
    logger.addHandler(alias_error_handler)

    # 5. Handler: Console (Human readable)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%H:%M:%S"))
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(console_handler)

    _logger_initialized = True
    _root_logger = logger

    logger.info(
        "Logger initialized",
        extra={
            "details": {
                "log_root": str(log_root.resolve()),
                "specific_log": str(full_log_path.relative_to(log_root)),
                "error_log": str(error_log_path.relative_to(log_root)),
                "level": level,
            }
        },
    )

    return logger


def get_logger(name: str = "sports_assistant") -> logging.Logger:
    """
    Get child logger from root logger.
    If root is not initialized, initialize with defaults.

    Args:
        name: Module name (e.g., 'sports_assistant.crawler')

    Returns:
        logging.Logger
    """
    global _logger_initialized
    if not _logger_initialized:
        setup_logger()

    if name == "sports_assistant":
        return logging.getLogger("sports_assistant")
    return logging.getLogger(f"sports_assistant.{name}")


# ---------------------------------------------------------------------------
#  Decorator: Deep Logging Wrapper
# ---------------------------------------------------------------------------

def log_function(logger_name: str = "sports_assistant"):
    """
    Decorator to wrap functions for full JSON logging:
      - timestamp
      - input (name + argument values)
      - output (return value)
      - error (exception if any)
      - latency_ms (execution time)

    Usage:
        @log_function("crawler")
        def crawl_articles(source: str) -> list:
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            _logger = get_logger(logger_name)
            func_name = f"{func.__module__}.{func.__qualname__}"

            # Capture inputs (sanitize large values)
            input_data = _sanitize_args(args, kwargs)

            start_time = time.perf_counter()
            result = None
            error_info = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                }
                raise
            finally:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

                # Sanitize output
                output_data = _sanitize_output(result)

                log_level = logging.ERROR if error_info else logging.INFO
                _logger.log(
                    log_level,
                    f"{'FAIL' if error_info else 'OK'} | {func_name}",
                    extra={
                        "input": input_data,
                        "output": output_data,
                        "error": error_info,
                        "latency_ms": elapsed_ms,
                    },
                )

        # Preserve original metadata
        wrapper.__name__ = func.__name__
        wrapper.__qualname__ = func.__qualname__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        return wrapper
    return decorator


def _sanitize_args(args: tuple, kwargs: dict) -> dict:
    """Truncate large values to prevent log bloat."""
    sanitized = {}
    for i, arg in enumerate(args):
        sanitized[f"arg_{i}"] = _truncate(arg)
    for k, v in kwargs.items():
        sanitized[k] = _truncate(v)
    return sanitized


def _sanitize_output(value: Any) -> Any:
    """Truncate large output."""
    return _truncate(value)


def _truncate(value: Any, max_len: int = 500) -> Any:
    """Truncate excessively long values for clean logs."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        if len(value) > max_len:
            return value[:max_len] + f"... [truncated, total {len(value)} chars]"
        return value
    if isinstance(value, (list, tuple)):
        length = len(value)
        if length > 10:
            return f"[{type(value).__name__}] {length} items"
        return str(value)[:max_len]
    if isinstance(value, dict):
        length = len(value)
        if length > 10:
            return f"[dict] {length} keys"
        return str(value)[:max_len]
    # Fallback
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "... [truncated]"
    return text
