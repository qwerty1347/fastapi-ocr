
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.services.auth.jwt import JwtService


jwt_service = JwtService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

def verify_access_token(token = Depends(oauth2_scheme)):
    return jwt_service.verify_access_token(token)