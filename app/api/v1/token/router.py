from fastapi import APIRouter

from app.services.auth.jwt import JwtService


router = APIRouter(prefix="/token", tags=["token"])
jwt_service = JwtService()

@router.post('/')
async def index():
    return jwt_service.create_access_token()