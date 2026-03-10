import logging

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstancePricing, InstanceType, Provider, Region
from app.services.demo_catalog import get_demo_recommendations

logger = logging.getLogger(__name__)


def _should_use_demo_catalog(exc: Exception) -> bool:
    if isinstance(exc, OSError):
        return True

    message = " ".join(
        str(part)
        for part in (exc, getattr(exc, "orig", None))
        if part
    ).lower()
    return any(
        marker in message
        for marker in (
            "connection refused",
            "could not connect",
            "failed to establish",
            "connection timed out",
            "timeout expired",
            "no such table",
            "does not exist",
            "undefined table",
        )
    )


async def get_recommendations(
    session: AsyncSession,
    cpu: int,
    ram: float,
    budget: float,
    region: str,
) -> list[dict]:
    region_pattern = f"%{region}%"
    region_match = or_(
        func.coalesce(Region.continent, "").ilike(region_pattern),
        func.coalesce(Region.country, "").ilike(region_pattern),
    )
    stmt = (
        select(
            Provider.name,
            InstanceType.instance_name,
            InstanceType.vcpu,
            InstanceType.ram_gb,
            InstancePricing.monthly_price_usd,
        )
        .join(InstanceType, InstancePricing.instance_type_id == InstanceType.id)
        .join(Region, InstancePricing.region_id == Region.id)
        .join(Provider, InstanceType.provider_id == Provider.id)
        .where(
            and_(
                InstanceType.vcpu >= cpu,
                InstanceType.ram_gb >= ram,
                InstancePricing.monthly_price_usd <= budget,
                region_match,
                InstanceType.is_active.is_(True),
            )
        )
        .order_by(asc(InstancePricing.monthly_price_usd))
        .limit(3)
    )
    try:
        result = await session.execute(stmt)
    except (DBAPIError, OSError) as exc:
        if not _should_use_demo_catalog(exc):
            raise

        # Keep /recommend usable in clean environments where Postgres
        # is not running yet or migrations have not been applied.
        logger.warning("Falling back to demo catalog: %s", exc)
        await session.rollback()
        return get_demo_recommendations(cpu=cpu, ram=ram, budget=budget, region=region)

    rows = result.all()
    return [
        {
            "provider": row.name,
            "instance": row.instance_name,
            "vcpu": row.vcpu,
            "ram": row.ram_gb,
            "price_monthly": round(row.monthly_price_usd, 2),
        }
        for row in rows
    ]
