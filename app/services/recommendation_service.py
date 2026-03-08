import logging

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InstancePricing, InstanceType, Provider, Region

logger = logging.getLogger(__name__)


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
        rows = result.all()
    except Exception:
        logger.exception("Recommendation query failed; returning no results")
        return []

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
