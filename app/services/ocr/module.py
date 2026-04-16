from fastapi import UploadFile

from app.core.logging import get_logger
from app.module.ocr.easyocr import EasyOcr

logger = get_logger()

class OcrModule:
    OCR_ENGINES = {
        "easyocr": EasyOcr()
    }

    def __init__(self, engine: str):
        self.engine = self.OCR_ENGINES[engine]


    async def recognize(self, file: UploadFile):
        return await self.engine.recognize(file)
