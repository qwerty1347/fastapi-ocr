from pydantic import BaseModel

from app.schemas.enums import OcrEngine


class OcrRequest(BaseModel):
    engine: OcrEngine