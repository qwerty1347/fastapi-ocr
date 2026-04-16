import pkgutil
import importlib

from fastapi import APIRouter


api_router = APIRouter(prefix="/v1")

for module in pkgutil.iter_modules(__path__):
    try:
        router_module = importlib.import_module(
            f"{__name__}.{module.name}.router"
        )
        api_router.include_router(router_module.router)

    except ModuleNotFoundError as e:
        print(f"{__name__}.{module.name} import 실패 {e}")
        continue