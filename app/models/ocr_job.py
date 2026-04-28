import enum

from sqlalchemy import JSON, Column, DateTime, Enum, String, func
from app.models.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"


class OcrJob(Base):
    __tablename__: str = "ocr_jobs"

    id = Column(String(50), primary_key=True, comment="UUID4")
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True, comment="OCR 상태: pending | started | success | failed")
    engine = Column(String(30), nullable=False, comment="OCR 엔진: easyocr | paddleocr | clovaocr")
    file_name = Column(String(255), nullable=False, comment="업로드 파일명")
    file_path = Column(String(512), nullable=False, comment="업로드 파일 경로")
    result = Column(JSON, nullable=True, comment="OCR 완료 결과")
    info = Column(JSON, nullable=True, comment="OCR 실패 시 메시지, 로그")
    created_at = Column(DateTime, default=func.now(), comment="생성 시간")
    started_at = Column(DateTime, nullable=True, comment="실행 시간")
    finished_at = Column(DateTime, nullable=True, comment="완료 시간")