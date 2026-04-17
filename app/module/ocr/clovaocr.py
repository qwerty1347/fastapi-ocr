import json
import time
import uuid

from fastapi import UploadFile

from app.core.config import config
from app.core.utils.file import get_file_extension
from app.core.utils.http_client import http_post
from app.module.ocr.base import BaseEngine


class ClovaOcr(BaseEngine):
    def __init__(self):
        pass


    async def recognize(self, file: UploadFile):
        post_url, files, headers = await self.build_form_data(file)
        ocr_result = await http_post(post_url, files=files, headers=headers)
        return self.parse_inferText(ocr_result)


    def convert_to_json(self):
        pass


    async def build_form_data(self, file: UploadFile):
        post_url: str = config.CLOVA_OCR_APIGW_INVOKE_URL
        file_bytes = await file.read()
        message = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": "ko",
            "images": [
                {
                    "format": get_file_extension(str(file.filename)),
                    "name": file.filename
                }
            ]
        }

        files: dict[str, tuple[str | None, bytes, str]] = {
            "file": (file.filename, file_bytes, file.content_type),
            "message": (None, json.dumps(message), "application/json")
        }

        headers = {
            "X-OCR-SECRET": config.CLOVA_OCR_SECRET_KEY,
        }

        return post_url, files, headers


    def parse_inferText(self, ocr_result) -> str:
        infer_texts =[]

        for image in ocr_result.get("images", []):
            for field in image.get("fields", []):
                infer_text = field.get("inferText")

                if infer_text:
                    infer_texts.append(infer_text)

        ocr_result['full_text'] = " ".join(infer_texts)

        return ocr_result