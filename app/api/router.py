from fastapi import APIRouter

from app.api.routes import recommend

api_router = APIRouter()
api_router.include_router(recommend.router)
