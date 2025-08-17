from pydantic import BaseModel

from app.domain.ocr.schemas.base import OcrResponseBase


class OcrItemResponse(BaseModel):
    ocr_result: dict


class OcrResponse(OcrResponseBase):
    data: dict