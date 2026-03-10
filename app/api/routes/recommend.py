from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.database import DbSession
from app.schemas.recommendation import RecommendRequest, RecommendResponse
from app.services.ollama_service import generate_explanation, parse_query_to_params
from app.services.recommendation_service import get_recommendations

router = APIRouter(prefix="/recommend", tags=["recommend"])

DEFAULT_CPU = 2
DEFAULT_RAM = 4.0
DEFAULT_BUDGET = 50.0
DEFAULT_REGION = "Europe"


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
    except (OperationalError, DBAPIError, OSError) as exc:
        # Surface database outages as a service dependency issue rather than
        # an unhandled exception that returns a generic 500.
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Please try again later.",
        ) from exc

    explanation: str | None = None
    if body.include_explanation and recommendations:
        explanation = await generate_explanation(recommendations)

    return RecommendResponse(recommendations=recommendations, explanation=explanation)
