from http import HTTPStatus
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions.custom import BusinessException
from app.core.utils.response import error_response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        message=str(exc)
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(
        code=exc.status_code,
        message=str(exc.detail)
    )


async def validation_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return error_response(
        code=HTTPStatus.UNPROCESSABLE_ENTITY,
        message="Validation Error",
        errors=[
            {
                "field": error["loc"],
                "message": error["msg"]
            }
            for error in exc.errors()
        ]
    )


async def jwt_exception_handler(request: Request, exc: JWTError):
    return error_response(
        code=HTTPStatus.UNAUTHORIZED,
        message="Could not validate credentials"
    )


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    return error_response(
        code=exc.code,
        message=exc.message,
        errors=exc.errors
    )


def add_exception_handlers(app):
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(JWTError, jwt_exception_handler)
    app.add_exception_handler(BusinessException, business_exception_handler)
