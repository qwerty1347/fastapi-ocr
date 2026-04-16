from fastapi.routing import APIRouter

from app.api___.v1 import api_v1_router


def get_api_routers() -> list[APIRouter]:
    """
    FastAPI 애플리케이션에 추가할 API Router 모음을 반환하는 함수

    반환값:
    - list[APIRouter]: API Router 모음
    """
    return [
        api_v1_router,
    ]