from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    DB_HOST: str
    DB_PORT: int
    DB_DATABASE: str
    DB_USERNAME: str
    DB_PASSWORD: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    JWT_EXPIRE_MINUTES: int
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_SUBJECT: str
    STORAGE_PATH: str
    CLOVA_OCR_APIGW_INVOKE_URL: str
    CLOVA_OCR_SECRET_KEY: str


config = Config()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_PATH = BASE_DIR / config.STORAGE_PATH