from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://copilot:copilot@localhost:5432/copilot",
        alias="DATABASE_URL",
    )
    jev_key: str | None = Field(default=None, alias="JEV_KEY")
    jev_model: str = Field(default="jev-1.13.0", alias="JEV_MODEL")
    redator: Literal["auto", "anthropic", "sem_llm"] = Field(default="auto", alias="REDATOR")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5-5", alias="ANTHROPIC_MODEL")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    corpus_dir: Path = Field(default=Path("corpus"), alias="CORPUS_DIR")
    fastembed_cache_path: Path = Field(
        default=Path(".cache/fastembed"), alias="FASTEMBED_CACHE_PATH"
    )

    @model_validator(mode="after")
    def _redator_com_a_chave_do_provedor(self) -> Self:
        if self.redator == "anthropic" and not self.anthropic_api_key:
            raise ValueError("REDATOR=anthropic exige ANTHROPIC_API_KEY")
        return self

def get_settings() -> Settings:
    return Settings()
