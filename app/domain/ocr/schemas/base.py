from pydantic import BaseModel


class OcrResponseBase(BaseModel):
    result: bool
    code: int