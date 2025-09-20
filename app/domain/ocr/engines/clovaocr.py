import json
import time
import uuid

from fastapi import UploadFile

from app.domain.ocr.engines.base_engine import BaseEngine
from common.helpers.http_client import http_post
from common.utils.file import get_file_extension
from config.settings import settings


class ClovaOcr(BaseEngine):
    def __init__(self):
        pass

    async def recognize(self, file: UploadFile) -> dict:
        post_url, files, headers = await self.build_form_data(file)
        return await http_post(post_url, files=files, headers=headers)


    def convert_to_json(self, ocr_result):
        pass


    async def build_form_data(self, file: UploadFile):
        post_url: str = settings.CLOVA_OCR_APIGW_INVOKE_URL
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
            "X-OCR-SECRET": settings.CLOVA_OCR_SECRET_KEY,
        }

        return post_url, files, headers
