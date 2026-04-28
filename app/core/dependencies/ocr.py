from fastapi import Form

from app.schemas.enums import OcrEngine
from app.schemas.ocr.request import OcrRequest


def parse_ocr_request(engine: OcrEngine = Form(...)) -> OcrRequest:
    """
    FastAPI Form으로부터 OcrEngine Enum을 입력받아, OcrRequest 객체를 생성하는 함수

    Args:
        engine (OcrEngine): easyocr or paddleocr or clovaocr

    Returns:
        OcrRequest: OcrRequest 객체
    """
    return OcrRequest(engine=engine)