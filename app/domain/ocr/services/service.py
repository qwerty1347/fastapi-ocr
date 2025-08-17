from fastapi import UploadFile

from app.domain.ocr.schemas.response import OcrItemResponse
from app.domain.ocr.modules.module import OcrModule


class OcrService():
    def __init__(self):
        pass

    async def handle_ocr(self, file: UploadFile, engine: str) -> OcrItemResponse:
        """
        주어진 파일에 대해 지정된 OCR 엔진을 사용하여 텍스트를 추출하는 비동기 함수

        매개변수:
        - file (UploadFile): 텍스트를 추출할 업로드된 파일
        - engine (str): 사용할 OCR 엔진의 이름

        반환값:
        - OcrItemResponse: 추출된 텍스트를 포함하는 OCR 응답 객체
        """
        ocr_engine = OcrModule(engine)
        ocr_result = await ocr_engine.recognize(file)

        return OcrItemResponse(ocr_result=ocr_result)