from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Literal
from fastapi import HTTPException
from jose import jwt

from config.settings import settings


class AuthService:
    def __init__(self):
        pass


    def create_access_token(self) -> dict[str, str]:
        """
        access_token을 생성하는 동기 메서드

        반환값:
        - dict[str, str]: 생성된 access_token이 포함된 성공 응답을 반환합니다.
        """
        data = {
            "sub": settings.JWT_SUBJECT,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        }

        return {
            "access_token": jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM),
            "token_type": "bearer",
        }


    def verify_access_token(self, token: str) -> bool:
        """
        access_token을 확인하는 동기 메서드

        매개변수:
        - token (str): 확인할 access_token

        반환값:
        - bool: access_token이 유효하면 True, 아니면 HTTPException 예외를 발생시킵니다.
        """
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        subject = payload.get('sub')

        if subject != settings.JWT_SUBJECT:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid token")

        return True