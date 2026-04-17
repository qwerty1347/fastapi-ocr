from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from fastapi import HTTPException
from jose import jwt

from app.core.config import config


class JwtService:
    def __init__(self):
        pass


    def create_access_token(self):
        """
        access_token을 생성하는 동기 메서드

        Returns:
        - dict[str, str]: 생성된 access_token이 포함된 성공 응답을 반환합니다.
        """

        data = {
            "sub": config.JWT_SUBJECT,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
        }

        return {
            "access_token": jwt.encode(data, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM),
            "token_type": "bearer"
        }



    def verify_access_token(self, token: str):
        """
        access_token을 확인하는 동기 메서드

        Args:
        - token (str): 확인할 access_token

        Returns:
        - bool: access_token이 유효하면 True, 아니면 HTTPException 예외를 발생시킵니다.
        """
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        subject = payload.get('sub')

        if subject != config.JWT_SUBJECT:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid token")

        return True