import logging
from typing import Any

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InstancePricing, InstanceType, Provider, Region

logger = logging.getLogger(__name__)

FALLBACK_CATALOG: list[dict[str, Any]] = [
    {
        "provider": "Hetzner",
        "instance": "CPX31",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 32.51,
        "regions": ["Europe", "Germany"],
    },
    {
        "provider": "OVHcloud",
        "instance": "b2-15",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 55.00,
        "regions": ["Europe", "France"],
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 96.00,
        "regions": ["Europe", "Netherlands", "Germany"],
    },
    {
        "provider": "Linode",
        "instance": "g6-standard-4",
        "vcpu": 4,
        "ram": 8.0,
        "price_monthly": 48.00,
        "regions": ["North America", "United States"],
    },
]


def _get_fallback_recommendations(
    cpu: int,
    ram: float,
    budget: float,
    region: str,
) -> list[dict[str, Any]]:
    normalized_region = region.strip().lower()
    matches: list[dict[str, Any]] = []
    for item in FALLBACK_CATALOG:
        if item["vcpu"] < cpu or item["ram"] < ram or item["price_monthly"] > budget:
            continue

        if normalized_region and not any(
            normalized_region in candidate.lower() for candidate in item["regions"]
        ):
            continue

        matches.append(
            {
                "provider": item["provider"],
                "instance": item["instance"],
                "vcpu": item["vcpu"],
                "ram": item["ram"],
                "price_monthly": round(item["price_monthly"], 2),
            }
        )

    return sorted(matches, key=lambda item: item["price_monthly"])[:3]


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
        await session.rollback()
        logger.warning(
            "Database unavailable for recommendations; serving fallback results: %s",
            exc,
        )
        return _get_fallback_recommendations(
            cpu=cpu,
            ram=ram,
            budget=budget,
            region=region,
        )
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
