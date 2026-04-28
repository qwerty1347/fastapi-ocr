from typing import Generic, TypeVar
from pydantic import BaseModel


T = TypeVar("T")

class SuccessResponse(BaseModel, Generic[T]):
    code: str
    data: T


class ErrorDetail(BaseModel):
    field: str | list[str] | None = None
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    errors: list[ErrorDetail] = []
