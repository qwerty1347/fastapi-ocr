from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.file import save_file
from app.models.ocr_job import OcrJob
from app.repositories.ocr import OcrRepository
from app.worker.tasks.ocr import run_ocr


class OcrJobService:
    def __init__(self, db: AsyncSession, ocr_repository: OcrRepository):
        self.db = db
        self.ocr_repository = ocr_repository


    async def create_ocr_job(self, file: UploadFile, engine: str) -> OcrJob:
        job = OcrJob(
            id=str(uuid4()),
            engine=engine,
            file_name=file.filename,
            file_path=str(await save_file(file))
        )
        ocr_job = await self.ocr_repository.create_ocr_job(job)
        await self.db.commit()
        run_ocr.delay(ocr_job.id)
        return ocr_job