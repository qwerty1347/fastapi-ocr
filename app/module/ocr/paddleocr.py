from fastapi import UploadFile
from paddleocr import PaddleOCR

from app.core.utils.file import delete_file, save_file
from app.module.ocr.base import BaseEngine


class PaddleOcr(BaseEngine):
    def __init__(self):
        self.ocr = PaddleOCR(lang='korean')


    async def recognize(self, file: UploadFile):
        file_path = await save_file(file)
        response = self.ocr.ocr(str(file_path))
        await delete_file(file_path)
        return self.convert_to_json(response)


    def convert_to_json(self, response):
        result = {"images": []}

        for line in response[0]:
            bounding_poly = line[0]
            text = line[1][0]
            confidence = float(line[1][1])

            result["images"].append({
                "boundingPoly": bounding_poly,
                "text": text,
                "confidence": confidence
            })

        return result