from abc import ABC, abstractmethod
from pathlib import Path


class BaseEngine(ABC):
    def __init__(self):
        pass


    @abstractmethod
    async def recognize(self, file_path: Path):
        pass


    @abstractmethod
    def convert_to_json(self, ocr_result) -> dict:
        pass