from http import HTTPStatus
from fastapi.responses import JSONResponse


def success_response(data: dict | None = None, code: int = HTTPStatus.OK) -> JSONResponse:
    """
    성공 응답을 반환하는 함수

    Args:
        data (dict | None): 성공 응답의 데이터. Defaults to None.
        code (int): 성공 응답의 상태 코드. Defaults to 200.

    Returns:
        JSONResponse: 성공 응답을 포함하는 FastAPI JSONResponse 객체.
    """
    if data is None:
        data = {}

    return JSONResponse(
        status_code=code,
        content={
            "code": str(code),
            "data": data
        }
    )


def error_response(code: int = HTTPStatus.INTERNAL_SERVER_ERROR, message: str | None = None, errors: list | None = None) -> JSONResponse:
    """
    오류 응답을 반환하는 함수

    Args:
        code (int): 에러 응답의 상태 코드. Defaults to 500.
        message (str | None): 에러 응답의 메시지. Defaults to None.
        errors (list | None): 에러 정보. Defaults to None.

    Returns:
        JSONResponse: 에러 응답을 포함하는 FastAPI JSONResponse 객체.
    """
    if message is None:
        message = "Internal Server Error"

    if not errors:
        errors = []

    return JSONResponse(
        status_code=code,
        content={
            "code": str(code),
            "message": message,
            "errors": errors
        }
    )