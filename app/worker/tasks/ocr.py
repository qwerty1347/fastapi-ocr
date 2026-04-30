from sqlalchemy import func

from app.infrastructure.database.session import sync_session_factory
from app.models.ocr_job import JobStatus, OcrJob
from app.worker.celery_app import celery


@celery.task
def run_ocr(job_id: str):
    with sync_session_factory() as session:
        ocr_job = session.get(OcrJob, job_id)

        if ocr_job is None:
            return

        ocr_job.status = JobStatus.STARTED
        ocr_job.result = "ocr result"
        ocr_job.started_at = func.now()

        try:
            # ! 작업해야함
            pass
        except Exception as e:
            ocr_job.status = JobStatus.FAILED
            ocr_job.info = {"error": "Unknown error", "message": str(e), "traceback": e.__traceback__}
            ocr_job.finished_at = func.now()
            session.commit()
        else:
            ocr_job.status = JobStatus.SUCCESS
            # ! 작업해야함
            # ocr_job.result =
            ocr_job.finished_at = func.now()
            session.commit()