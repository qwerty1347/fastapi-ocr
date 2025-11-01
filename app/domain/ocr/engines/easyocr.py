import easyocr

from fastapi import UploadFile

from app.domain.ocr.engines.base_engine import BaseEngine
from common.helpers.file import delete_file, save_file


class EasyOcr(BaseEngine):
    def __init__(self):
        self.easyocr = easyocr.Reader(['ko', 'en'])

    async def recognize(self, file: UploadFile) -> dict:
        file_path = await save_file(file)
        ocr_result = self.convert_to_json(self.easyocr.readtext(str(file_path)))
        await delete_file(file_path)
        return ocr_result


    def convert_to_json(self, ocr_result) -> dict:
        result = {
            "images": [],
        }
        full_text = ""

        for poly, text, confidence in ocr_result:
            bounding_poly: list[list[int]] = [[int(vertex[0]), int(vertex[1])] for vertex in poly]
            result["images"].append({
                "boundingPoly": bounding_poly,
                "text": text,
                "confidence": float(confidence)
            })
            full_text += text + " "

        result["full_text"] = full_text

        return result