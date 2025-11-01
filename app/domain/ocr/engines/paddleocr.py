from fastapi import UploadFile
from paddleocr import PaddleOCR

from app.domain.ocr.engines.base_engine import BaseEngine
from common.helpers.file import delete_file, save_file


class PaddleOcr(BaseEngine):
    def __init__(self):
        self.paddleocr = PaddleOCR(lang='korean', use_angle_cls=False)

    async def recognize(self, file: UploadFile) -> dict:
        file_path = await save_file(file)
        ocr_result = self.convert_to_json(self.paddleocr.ocr(str(file_path)))
        await delete_file(file_path)
        return ocr_result


    def convert_to_json(self, ocr_result) -> dict:
        result = {
            "images": []
        }
        full_text = ""

        polys = ocr_result[0].get("rec_polys", [])
        texts = ocr_result[0].get("rec_texts", [])
        confidences = ocr_result[0].get("rec_scores", [])

        for poly, text, confidence in zip(polys, texts, confidences):
            bounding_poly = poly.tolist() if hasattr(poly, "tolist") else poly
            result["images"].append({
                "boundingPoly": bounding_poly,
                "text": text,
                "confidence": float(confidence)
            })
            full_text += text + " "

        result["full_text"] = full_text

        return result