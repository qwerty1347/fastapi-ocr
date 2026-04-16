from enum import Enum


class OcrEngine(str, Enum):
    easyocr: str = "easyocr"
    paddleocr: str = "paddleocr"
    clovaocr: str = "clovaocr"