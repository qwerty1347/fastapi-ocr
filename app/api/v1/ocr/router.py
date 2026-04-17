from fastapi import APIRouter, Depends, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.utils.response import success_response
from app.dependencies.auth import verify_access_token
from app.dependencies.file import get_ocr_validated_file
from app.dependencies.ocr import parse_ocr_request
from app.schemas.common import ErrorResponse
from app.schemas.ocr.request import OcrRequest
from app.schemas.ocr.response import OcrResponse
from app.services.ocr.ocr import OcrService


router = APIRouter(prefix="/ocr", tags=["OCR"])
ocr_service = OcrService()

@router.get('/')
def index():
    return {"message": "Hello OCR"}


@router.post(
    '/',
    response_model=OcrResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(verify_access_token)],
)
async def do_ocr(
    file: UploadFile = Depends(get_ocr_validated_file),
    ocr_dto: OcrRequest = Depends(parse_ocr_request)
) -> JSONResponse:
    result = await ocr_service.do_ocr(file, ocr_dto.engine.value)
    return success_response(jsonable_encoder(result))