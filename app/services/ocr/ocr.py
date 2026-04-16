from fastapi import UploadFile

from app.core.logging import get_logger
from app.services.ocr.module import OcrModule


class OcrService():
    def __init__(self):
        pass


    async def do_ocr(self, file: UploadFile, engine: str):
        ocr_engine = OcrModule(engine)
        result = await ocr_engine.recognize(file)
        get_logger().info(r)
        return result
