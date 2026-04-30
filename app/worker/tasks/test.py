from app.worker.celery_app import celery


@celery.task
def add_number(x: int, y: int) -> int:
    return x + y