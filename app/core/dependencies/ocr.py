from fastapi import Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.database import get_database
from app.repositories.ocr import OcrRepository
from app.schemas.enums import OcrEngine
from app.schemas.ocr.request import OcrRequest
from app.services.ocr.job import OcrJobService
from app.services.ocr.ocr import OcrService


def parse_ocr_request(engine: OcrEngine = Form(...)) -> OcrRequest:
    """
    FastAPI Form으로부터 OcrEngine Enum을 입력받아, OcrRequest 객체를 생성하는 함수

    Args:
        engine (OcrEngine): easyocr or paddleocr or clovaocr

    Returns:
        OcrRequest: OcrRequest 객체
    """
    return OcrRequest(engine=engine)


def get_ocr_service() -> OcrService:
    return OcrService()


def get_ocr_repository(db: AsyncSession = Depends(get_database)) -> OcrRepository:
    return OcrRepository(db)


def get_ocr_job_service(db: AsyncSession = Depends(get_database)) -> OcrJobService:
    return OcrJobService(db, OcrRepository(db))