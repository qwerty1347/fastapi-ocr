from fastapi import UploadFile

from app.services.ocr.module import OcrModule


class OcrService():
    def __init__(self):
        pass


    async def do_ocr(self, file: UploadFile, engine: str):
        """
        OCR을 수행하는 함수

        Args:
            file (UploadFile): OCR을 수행할 업로드 파일
            engine (str): OCR 엔진 (easyocr, paddleocr, clovaocr)

        Returns:
            dict: OCR 수행 결과
        """
        ocr_engine = OcrModule(engine)
        result = await ocr_engine.recognize(file)
        return result


    def do_job_ocr(self):
        pass