"""
全局配置：所有环境变量集中在此读取，避免散落。
通过 pydantic-settings 自动做类型校验与默认值处理。
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str = "dev-secret-change-me-please-at-least-32-characters"
    APP_PORT: int = 8000
    APP_CORS_ORIGINS: str = "http://localhost:3000"

    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "training"
    POSTGRES_USER: str = "training"
    POSTGRES_PASSWORD: str = "training_dev_pwd"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "training-materials"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    AI_PROVIDER: Literal["deepseek", "openai", "qwen", "custom"] = "deepseek"
    AI_MODEL_CHAT: str = "deepseek-chat"
    AI_MODEL_EMBEDDING: str = "text-embedding-v2"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    DASHSCOPE_API_KEY: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    SMTP_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    AUTH_REGISTER_CODE_TTL_MINUTES: int = 10
    AUTH_REGISTER_CODE_RESEND_SECONDS: int = 60

    EMBEDDING_DIM: int = 1536
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 80
    RAG_TOP_K: int = 5
    # PDF OCR 兜底：扫描版 PDF 无文字层时自动 OCR 再切片
    PDF_OCR_FALLBACK_ENABLED: bool = True
    PDF_OCR_LANG: str = "chi_sim+eng"
    PDF_OCR_DPI: int = 220
    PDF_OCR_MAX_PAGES: int = 120

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def database_url_sync(self) -> str:
        return self.database_url

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
