from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import yaml, os


# --- config.yaml models ---

class AlbertConfig(BaseModel):
    base_url: str
    auth_url: str
    app_version: str
    build_version: str


class Config(BaseModel):
    albert: AlbertConfig


# --- .env settings ---

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql://grocery:grocery@localhost:5432/grocery"
    anthropic_api_key: str = ""

    albert_token: str = ""
    albert_refresh_token: str = ""
    albert_client_credentials: str = ""

    lidl_refresh_token: str = ""
    lidl_country: str = "CZ"
    lidl_language: str = "cs"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_config() -> Config:
    path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(path) as f:
        return Config.model_validate(yaml.safe_load(f))
