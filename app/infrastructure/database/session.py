from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import config


def _build_url(driver: str):
    return (
        f"mysql+{driver}://{config.DB_USERNAME}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_DATABASE}"
        f"?charset=utf8mb4"
    )


SYNC_DATABASE_URL = _build_url("pymysql")
ASYNC_DATABASE_URL = _build_url("aiomysql")


async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,     # 끊긴 커넥션 자동 회복
    pool_recycle=3600,      # MySQL wait_timeout보다 짧게
    pool_size=10,
    max_overflow=20,
)


async_session_factory = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    autoflush=False,
)


sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)


sync_session_factory = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autoflush=False
)