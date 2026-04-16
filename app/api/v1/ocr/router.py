
import logging

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies.file import get_ocr_validated_file
from app.dependencies.ocr import parse_ocr_request
from app.schemas.ocr.request import OcrRequest


router = APIRouter(prefix="/ocr", tags=["OCR"])
logger = logging.getLogger(__name__)


@router.get('/')
def index():
    return {"message": "Hello OCR"}


@router.post('/')
async def do_ocr(
    file: UploadFile = Depends(get_ocr_validated_file),
    ocr_dto: OcrRequest = Depends(parse_ocr_request)
):
    logger.info(ocr_dto)
    return {"message": "OCR"}