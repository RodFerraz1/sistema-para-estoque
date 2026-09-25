from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://copilot:copilot@localhost:5432/copilot",
        alias="DATABASE_URL",
    )
    jev_key: str | None = Field(default=None, alias="JEV_KEY")
    jev_model: str = Field(default="jev-latest", alias="JEV_MODEL")


def get_settings() -> Settings:
    return Settings()
