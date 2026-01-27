"""Application settings loaded from environment."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed settings for the pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    pghost: Optional[str] = Field(default=None, alias="PGHOST")
    pgport: int = Field(default=5432, alias="PGPORT")
    pguser: Optional[str] = Field(default=None, alias="PGUSER")
    pgpassword: Optional[str] = Field(default=None, alias="PGPASSWORD")
    pgdatabase: Optional[str] = Field(default=None, alias="PGDATABASE")

    # Supabase
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: Optional[str] = Field(
        default=None, alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_anon_key: Optional[str] = Field(default=None, alias="SUPABASE_ANON_KEY")

    # Open311
    open311_base_url: str = Field(
        default="https://sags-uns.stadt-koeln.de/georeport/v2",
        alias="OPEN311_BASE_URL",
    )
    open311_timeout_seconds: int = Field(default=30, alias="OPEN311_TIMEOUT_SECONDS")
    open311_page_size: int = Field(default=100, alias="OPEN311_PAGE_SIZE")
    open311_use_extensions: bool = Field(default=True, alias="OPEN311_USE_EXTENSIONS")
    open311_max_workers: int = Field(default=10, alias="OPEN311_MAX_WORKERS")
    open311_max_retries: int = Field(default=3, alias="OPEN311_MAX_RETRIES")

    # Ingestion
    ingestion_overlap_hours: int = Field(default=12, alias="INGESTION_OVERLAP_HOURS")
    ingestion_enable_gap_fill: bool = Field(default=True, alias="INGESTION_ENABLE_GAP_FILL")
    ingestion_gap_fill_limit: int = Field(default=5000, alias="INGESTION_GAP_FILL_LIMIT")
    duplicate_window_hours: int = Field(default=24, alias="DUPLICATE_WINDOW_HOURS")
    duplicate_coord_precision: int = Field(default=4, alias="DUPLICATE_COORD_PRECISION")
    duplicate_require_service_name: bool = Field(
        default=True, alias="DUPLICATE_REQUIRE_SERVICE_NAME"
    )
    duplicate_require_address: bool = Field(default=False, alias="DUPLICATE_REQUIRE_ADDRESS")
    link_only_min_chars: int = Field(default=3, alias="LINK_ONLY_MIN_CHARS")

    # LLM providers
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_model_id: str = Field(default="gemini-2.5-flash-lite", alias="GEMINI_MODEL_ID")
    gemini_api_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        alias="GEMINI_API_BASE_URL",
    )
    gemini_temperature: float = Field(default=0.0, alias="GEMINI_TEMPERATURE")
    gemini_max_output_tokens: int = Field(default=512, alias="GEMINI_MAX_OUTPUT_TOKENS")
    labeling_sleep_seconds: float = Field(default=0.1, alias="LABELING_SLEEP_SECONDS")
    labeling_max_retries: int = Field(default=2, alias="LABELING_MAX_RETRIES")
    phase1_prompt_version: str = Field(default="p1_v006", alias="PHASE1_PROMPT_VERSION")
    phase2_prompt_version: str = Field(default="p2_v001", alias="PHASE2_PROMPT_VERSION")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")

    # Langfuse tracing
    langfuse_public_key: Optional[str] = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")

    # Runtime
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    run_env: str = Field(default="local", alias="RUN_ENV")

    def get_database_url(self) -> str:
        """Return a usable database URL or raise."""
        if self.database_url:
            return self.database_url

        if all([self.pghost, self.pguser, self.pgpassword, self.pgdatabase]):
            return (
                "postgresql://"
                f"{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/"
                f"{self.pgdatabase}"
            )

        raise ValueError("DATABASE_URL or PG* env vars must be set")
