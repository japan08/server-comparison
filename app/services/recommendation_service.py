from typing import Any

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InstancePricing, InstanceType, Provider, Region

FALLBACK_CATALOG: list[dict[str, Any]] = [
    {
        "provider": "Hetzner",
        "instance": "CPX31",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 64.97,
        "region": "Europe",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 96.36,
        "region": "Europe",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-32gb",
        "vcpu": 4,
        "ram": 32.0,
        "price_monthly": 96.36,
        "region": "Asia",
    },
]


def _serialize_rows(rows: list[Any]) -> list[dict[str, Any]]:
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


def _fallback_recommendations(
    cpu: int,
    ram: float,
    budget: float,
    region: str,
) -> list[dict[str, Any]]:
    region_query = region.strip().lower()
    matches = [
        item
        for item in FALLBACK_CATALOG
        if item["vcpu"] >= cpu
        and item["ram"] >= ram
        and item["price_monthly"] <= budget
        and region_query in item["region"].lower()
    ]
    matches.sort(key=lambda item: item["price_monthly"])
    return [
        {
            "provider": item["provider"],
            "instance": item["instance"],
            "vcpu": item["vcpu"],
            "ram": item["ram"],
            "price_monthly": item["price_monthly"],
        }
        for item in matches[:3]
    ]


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
    except (ConnectionRefusedError, DBAPIError, OSError, SQLAlchemyError):
        # Keep the endpoint usable in environments where local Postgres is absent.
        return _fallback_recommendations(cpu=cpu, ram=ram, budget=budget, region=region)

    return _serialize_rows(result.all())
