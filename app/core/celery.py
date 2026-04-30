from celery import Celery

from app.core.config import config

celery_app = Celery(
    "worker",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_BROKER_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
)

celery_app.autodiscover_tasks(["app.tasks"])