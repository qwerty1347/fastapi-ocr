from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    JWT_EXPIRE_MINUTES: int
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_SUBJECT: str
    CLOVA_OCR_APIGW_INVOKE_URL: str
    CLOVA_OCR_SECRET_KEY: str
    STORAGE_PATH: str
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"


config = Config()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_PATH = BASE_DIR / config.STORAGE_PATH