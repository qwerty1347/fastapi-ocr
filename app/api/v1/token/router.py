from fastapi import APIRouter

from app.schemas.token.response import JwtResponse
from app.services.auth.jwt import JwtService


router = APIRouter(prefix="/token", tags=["token"])
jwt_service = JwtService()

@router.post('/', response_model=JwtResponse)
async def create_jwt():
    return jwt_service.create_access_token()