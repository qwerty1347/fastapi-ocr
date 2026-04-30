from fastapi import APIRouter, Depends, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.utils.response import success_response
from app.core.dependencies.auth import verify_access_token
from app.core.dependencies.file import get_ocr_validated_file
from app.core.dependencies.ocr import get_ocr_job_service, get_ocr_service, parse_ocr_request
from app.schemas.base import ErrorResponse
from app.schemas.ocr.request import OcrRequest
from app.schemas.ocr.response import OcrResponse
from app.services.ocr.job import OcrJobService
from app.services.ocr.ocr import OcrService


router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.post(
    '/',
    response_model=OcrResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[Depends(verify_access_token)],
)
async def do_ocr(
    file: UploadFile = Depends(get_ocr_validated_file),
    ocr_dto: OcrRequest = Depends(parse_ocr_request),
    ocr_service: OcrService = Depends(get_ocr_service)
) -> JSONResponse:
    result = await ocr_service.do_ocr(file, ocr_dto.engine.value)
    return success_response(jsonable_encoder(result))


@router.post('/jobs')
async def create_ocr_job(
    file: UploadFile = Depends(get_ocr_validated_file),
    ocr_dto: OcrRequest = Depends(parse_ocr_request),
    ocr_job_service: OcrJobService = Depends(get_ocr_job_service)
):
    await ocr_job_service.create_ocr_job(file, ocr_dto.engine.value)
    return {"message": "test"}


@router.get('/jobs/{id}')
async def get_ocr_job_result():
    pass