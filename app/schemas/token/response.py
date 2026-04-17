from pydantic import BaseModel


class JwtResponse(BaseModel):
    access_token: str
    token_type: str