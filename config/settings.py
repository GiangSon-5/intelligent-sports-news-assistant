"""
Config Module — settings.py
Pydantic Settings class with type-safe validation, singleton pattern,
and business rules enforcement according to SPEC/SRS.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from logger import get_logger, log_function

_log = get_logger("config")


class AppSettings(BaseSettings):
    """
    Root configuration class.
    Load from .env file or OS environment variables.
    Priority: OS Env Var > .env file > Default value.
    """

    # --- Environment ---
    ENV: Literal["DEV", "PRODUCTION"] = "DEV"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- AI Configuration ---
    GEMINI_API_KEY: str
    OPENAI_API_KEY: str = ""
    PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_FALLBACK_MODELS: str = "gemini-3-flash,gemini-2.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b-it,gemma-3-27b-it"
    FALLBACK_MODEL: str = "gpt-4o"
    ENABLE_FALLBACK: bool = True

    # --- Crawler Configuration ---
    CONCURRENT_REQUESTS: int = 16
    DOWNLOAD_DELAY: float = 0.5
    CRAWL_DAYS_BACK: int = 7
    TARGET_SOURCES: list[str] = [
        "https://vnexpress.net/the-thao",
        "https://thanhnien.vn/the-thao",
        "https://tuoitre.vn/the-thao.htm",
    ]

    # --- Storage Paths ---
    RAW_DATA_DIR: str = "storage/raw"
    PROCESSED_DATA_DIR: str = "storage/processed"
    REPORTS_DIR: str = "storage/reports"
    LOGS_DIR: str = "logs"

    # --- AI Processing ---
    MAX_ARTICLES_PER_SUMMARY: int = 50
    SUMMARY_MAX_TOKENS: int = 1024
    KEYWORD_EXTRACTION_COUNT: int = 15
    TOP_HIGHLIGHTED_NEWS: int = 10

    # --- Retry & Timeout ---
    API_TIMEOUT_SECONDS: int = 30
    API_MAX_RETRIES: int = 3
    API_RETRY_DELAY: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    #  Field Validators (Business Rules from SPEC §3.3)
    # ------------------------------------------------------------------

    @field_validator("CONCURRENT_REQUESTS")
    @classmethod
    def validate_concurrent_requests(cls, v: int) -> int:
        if not 1 <= v <= 64:
            raise ValueError("CONCURRENT_REQUESTS must be between 1 and 64")
        return v

    @field_validator("DOWNLOAD_DELAY")
    @classmethod
    def validate_download_delay(cls, v: float) -> float:
        if not 0.0 <= v <= 10.0:
            raise ValueError("DOWNLOAD_DELAY must be between 0.0 and 10.0")
        return v

    @field_validator("CRAWL_DAYS_BACK")
    @classmethod
    def validate_crawl_days_back(cls, v: int) -> int:
        if not 1 <= v <= 30:
            raise ValueError("CRAWL_DAYS_BACK must be between 1 and 30")
        return v

    @field_validator("GEMINI_API_KEY")
    @classmethod
    def validate_gemini_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GEMINI_API_KEY is required and cannot be empty")
        return v.strip()

    # ------------------------------------------------------------------
    #  Model Validator — cross-field logic (SRS Business Rule #2)
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def validate_fallback_requires_openai_key(self) -> "AppSettings":
        """
        Business Rule: When ENABLE_FALLBACK=true, OPENAI_API_KEY is mandatory.
        """
        if self.ENABLE_FALLBACK and (not self.OPENAI_API_KEY or not self.OPENAI_API_KEY.strip()):
            raise ValueError(
                "OPENAI_API_KEY is required when ENABLE_FALLBACK is true. "
                "Set ENABLE_FALLBACK=false or provide a valid OPENAI_API_KEY."
            )
        return self

    @model_validator(mode="after")
    def enforce_production_delay(self) -> "AppSettings":
        """
        Business Rule #4 (SRS): ENV=PRODUCTION → DOWNLOAD_DELAY minimum 1.0s.
        """
        if self.ENV == "PRODUCTION" and self.DOWNLOAD_DELAY < 1.0:
            self.DOWNLOAD_DELAY = 1.0
        return self

    # ------------------------------------------------------------------
    #  Helper Methods (SPEC §3.2)
    # ------------------------------------------------------------------

    def get_active_model(self) -> str:
        """Returns the active model name (primary)."""
        return self.PRIMARY_MODEL

    def get_gemini_fallbacks(self) -> list[str]:
        """Split GEMINI_FALLBACK_MODELS into a list for the Chain."""
        if not self.GEMINI_FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.GEMINI_FALLBACK_MODELS.split(",") if m.strip()]

    def get_fallback_model(self) -> str | None:
        """Returns fallback model if enabled, else None."""
        if self.ENABLE_FALLBACK and self.OPENAI_API_KEY:
            return self.FALLBACK_MODEL
        return None


@lru_cache()
def get_settings() -> AppSettings:
    """
    Singleton factory — ensure config is loaded only once.
    Other modules import:
        from config.settings import get_settings
        settings = get_settings()

    Raises:
        ValidationError: When config is missing or incorrect. The system stops immediately (fail-fast).
    """
    try:
        settings = AppSettings()
        _log.info(
            "Configuration loaded successfully",
            extra={
                "details": {
                    "env": settings.ENV,
                    "primary_model": settings.PRIMARY_MODEL,
                    "fallback_enabled": settings.ENABLE_FALLBACK,
                    "fallback_model": settings.get_fallback_model(),
                    "concurrent_requests": settings.CONCURRENT_REQUESTS,
                    "crawl_days_back": settings.CRAWL_DAYS_BACK,
                }
            },
        )
        return settings
    except Exception as e:
        _log.error(
            "Configuration load FAILED — system cannot start",
            extra={"error": {"type": type(e).__name__, "message": str(e)}},
        )
        raise
