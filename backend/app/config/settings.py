
from functools import lru_cache
from pathlib import Path

#we are using cache because what if we are pulling 5 different spotufy credential
#Instead of repeadiatily pulling them from env, they can use all the same settings instance
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8001/auth/callback"
    frontend_url: str = "http://127.0.0.1:5173"
    cookie_secure: bool = False
    session_secret: str = ""
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'spotify_wrapped.db').as_posix()}"

    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
