from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.domain.auth.dependencies.dependency import verify_access_token
from app.domain.ocr.dependencies.dependency import parse_ocr_request
from app.domain.ocr.schemas.request import OcrRequest
from app.domain.ocr.schemas.response import OcrResponse
from app.domain.ocr.services.service import OcrService
from app.domain.ocr.validators.file import validate_upload_file
from common.constants.route import RouteConstants
from common.utils.response import success_response


router = APIRouter(prefix=RouteConstants.OCR_PREFIX, tags=[RouteConstants.OCR_TAG])
ocr_service = OcrService()


@router.post('/', response_model=OcrResponse)
async def ocr(
    token: bool = Depends(verify_access_token),
    file: UploadFile = File(...),
    ocr_dto: OcrRequest = Depends(parse_ocr_request)
) -> JSONResponse:
    """
    업로드된 파일을 처리하고 OCR 요청을 수행하는 비동기 함수

    매개변수:
    - file (UploadFile): OCR을 수행할 업로드된 파일
    - ocr_dto (OcrRequest): OCR 요청 데이터 전송 객체

    반환값:
    - JSONResponse: OCR 결과를 포함하는 성공 응답 또는 오류 응답
    """
    validate_upload_file(file)
    response = await ocr_service.handle_ocr(file, ocr_dto.engine.value)

    return success_response(jsonable_encoder(response))