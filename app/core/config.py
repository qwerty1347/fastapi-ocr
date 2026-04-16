from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    STORAGE_PATH: str


config = Config()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_PATH = BASE_DIR / config.STORAGE_PATH