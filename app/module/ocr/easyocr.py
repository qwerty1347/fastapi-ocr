import easyocr

from fastapi import UploadFile

from app.core.logging import get_logger
from app.core.utils.file import delete_file, save_file
from app.module.ocr.base import BaseEngine

logger = get_logger()
class EasyOcr(BaseEngine):
    def __init__(self):
        self.ocr = easyocr.Reader(['ko', 'en'])


    async def recognize(self, file: UploadFile):
        file_path = await save_file(file)
        logger.info(file_path)
        response = self.ocr.readtext(str(file_path))
        result = self.convert_to_json(response)
        await delete_file(file_path)
        return result


    def convert_to_json(self, response):
        result = {
            "images": []
        }

        for poly, text, confidence in response:
            bounding_poly = [[int(vertex[0]), int(vertex(1))] for vertex in poly]
            result['images'].append({
                "boundingPoly": bounding_poly,
                "text": text,
                "confidence": float(confidence)
            })

        return result