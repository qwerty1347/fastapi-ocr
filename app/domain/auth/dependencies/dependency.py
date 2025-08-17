from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.domain.auth.services.service import AuthService


auth_service = AuthService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")


def verify_access_token(token: str = Depends(oauth2_scheme)) -> bool:
    """
    access_token을 검증하는 동기 메서드

    매개변수:
    - token (str): 검증할 access_token

    반환값:
    - bool: access_token이 유효하면 True, 아니면 HTTPException 예외를 발생시킵니다.
    """
    return auth_service.verify_access_token(token)