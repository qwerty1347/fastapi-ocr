from fastapi import APIRouter

from app.domain.auth.services.service import AuthService


router = APIRouter(prefix="/token", tags=["token"])
auth_service = AuthService()


@router.post('/')
async def index() -> dict[str, str]:
    """
    access_token을 생성하는 동기 메서드

    반환값:
    - dict[str, str]: 생성된 access_token이 포함된 성공 응답을 반환합니다.
    """
    return auth_service.create_access_token()