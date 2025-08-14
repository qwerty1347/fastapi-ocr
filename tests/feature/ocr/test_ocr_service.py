import pytest

from pathlib import Path
from fastapi import UploadFile

from app.domain.ocr.services.service import OcrService


@pytest.mark.asyncio
class TestOcrService:
    async def async_setup(self):
        self.service = OcrService()
        self.file_path = Path("storage") / "uploads" / "ocr" / "test.jpg"
        self.engine = "easyocr"
        
        
    async def test_handle_ocr(self):
        await self.async_setup()
        file = UploadFile(filename="test.jpg", file=open(self.file_path, "rb"))
        response = await self.service.handle_ocr(file, self.engine)

        print(response)
        assert isinstance(response.ocr_result['images'], list)