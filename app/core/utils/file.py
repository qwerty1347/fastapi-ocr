import time

from fastapi import UploadFile
from pathlib import Path

from app.core.config import config


def get_file_extension(file_name: str) -> str:
    """
    업로드 파일의 확장자를 반환하는 함수

    Args:
        file_name (str): 업로드 파일의 이름

    Returns:
        str: 업로드 파일의 확장자명
    """
    return Path(file_name).suffix.lstrip('.')


def is_allowed_extension(file_name: str, allowed_extension) -> bool:
    """
    업로드 파일의 확장자가 허용된 목록인지 확인하는 함수

    Args:
        file_name (str): 업로드 파일의 이름
        allowed_extensions (set[str]): 허용된 확장자 목록

    Returns:
        bool: 허용된 확장자 목록에 포함되어 있으면 True, 아니면 False
    """
    file_extension = get_file_extension(file_name)
    return file_extension in allowed_extension


async def save_file(file: UploadFile) -> Path:
    """
    주어진 업로드 파일을 저장하는 함수

    매개변수:
    - file (UploadFile): 저장할 업로드 파일

    반환값:
    - Path: 저장된 파일의 경로
    """
    upload_dir = Path(config.STORAGE_PATH) / "uploads" / "ocr"
    file_name = f"{int(time.time())}.{get_file_extension(file.filename)}"
    file_path = upload_dir / file_name

    upload_dir.mkdir(parents=True, exist_ok=True)

    with file_path.open('wb') as f:
        content = await file.read()
        f.write(content)

    return file_path


async def delete_file(file_path: Path):
    """
    주어진 파일 경로의 파일을 삭제하는 함수

    매개변수:
    - file_path (Path): 삭제할 파일의 경로
    """
    if file_path.exists():
        file_path.unlink()
