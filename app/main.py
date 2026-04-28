from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.core.exceptions.handlers import add_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
add_exception_handlers(app)

@app.get('/')
def index():
    return {"message": "Hello FastAPI"}