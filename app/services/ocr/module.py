from fastapi import UploadFile

from app.module.ocr.clovaocr import ClovaOcr
from app.module.ocr.easyocr import EasyOcr
from app.module.ocr.paddleocr import PaddleOcr


class OcrModule:
    OCR_ENGINES = {
        "easyocr": EasyOcr(),
        "paddleocr": PaddleOcr(),
        "clovaocr": ClovaOcr()
    }

    def __init__(self, engine: str):
        self.engine = self.OCR_ENGINES[engine]


    async def recognize(self, file: UploadFile):
        """
        OCR 엔진을 사용하여 업로드된 이미지 파일에서 텍스트를 추출하는 함수

        Args:
            file (UploadFile): 업로드 이미지 파일

        Returns:
            dict: 추출된 텍스트 정보
        """
        return await self.engine.recognize(file)