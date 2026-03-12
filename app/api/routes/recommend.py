import logging
from contextlib import suppress

from fastapi import APIRouter
from sqlalchemy.exc import DBAPIError

from app.core.database import DbSession
from app.schemas.recommendation import RecommendRequest, RecommendResponse
from app.services.ollama_service import generate_explanation, parse_query_to_params
from app.services.recommendation_service import get_recommendations

router = APIRouter(prefix="/recommend", tags=["recommend"])
logger = logging.getLogger(__name__)

DEFAULT_CPU = 2
DEFAULT_RAM = 4.0
DEFAULT_BUDGET = 50.0
DEFAULT_REGION = "Europe"


def _is_database_connection_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (OSError, TimeoutError)):
            return True
        if isinstance(current, DBAPIError) and current.connection_invalidated:
            return True
        message = str(current).lower()
        if "connection refused" in message or "could not connect" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


@router.post("", response_model=RecommendResponse)
async def recommend(
    body: RecommendRequest,
    session: DbSession,
) -> RecommendResponse:
    if body.query:
        params = await parse_query_to_params(body.query)
        if params:
            cpu = params["cpu"]
            ram = params["ram"]
            budget = params["budget"]
            region = params["region"]
        else:
            cpu = body.cpu if body.cpu is not None else DEFAULT_CPU
            ram = body.ram if body.ram is not None else DEFAULT_RAM
            budget = body.budget if body.budget is not None else DEFAULT_BUDGET
            region = (body.region or "").strip() or DEFAULT_REGION
    else:
        cpu = body.cpu
        ram = body.ram
        budget = body.budget
        region = (body.region or "").strip() or DEFAULT_REGION

    try:
        recommendations = await get_recommendations(
            session=session,
            cpu=cpu,
            ram=ram,
            budget=budget,
            region=region,
        )
    except Exception as exc:
        if not _is_database_connection_error(exc):
            raise
        # Keep the API responsive when local Postgres is unavailable.
        with suppress(Exception):
            await session.rollback()
        logger.warning("Database unavailable during recommendation lookup: %s", exc)
        recommendations = []

    explanation: str | None = None
    if body.include_explanation and recommendations:
        explanation = await generate_explanation(recommendations)

    return RecommendResponse(recommendations=recommendations, explanation=explanation)
