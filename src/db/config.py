from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://copilot:copilot@localhost:5432/copilot",
        alias="DATABASE_URL",
    )


def get_settings() -> Settings:
    return Settings()
