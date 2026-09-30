from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://copilot:copilot@localhost:5432/copilot",
        alias="DATABASE_URL",
    )
    jev_key: str | None = Field(default=None, alias="JEV_KEY")
    jev_model: str = Field(default="jev-1.13.0", alias="JEV_MODEL")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    corpus_dir: Path = Field(default=Path("corpus"), alias="CORPUS_DIR")
    fastembed_cache_path: Path = Field(
        default=Path(".cache/fastembed"), alias="FASTEMBED_CACHE_PATH"
    )


def get_settings() -> Settings:
    return Settings()
