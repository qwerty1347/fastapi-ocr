from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ocr_job import OcrJob


class OcrRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def create_ocr_job(self, ocr_job: OcrJob):
        self.db.add(ocr_job)
        return ocr_job