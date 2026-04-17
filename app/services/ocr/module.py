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
        return await self.engine.recognize(file)
