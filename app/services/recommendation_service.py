from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InstancePricing, InstanceType, Provider, Region

FALLBACK_CATALOG = [
    {
        "provider": "Hetzner",
        "instance": "CPX31",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 64.97,
        "continent": "Europe",
        "country": "Germany",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 96.36,
        "continent": "Europe",
        "country": "Germany",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-32gb",
        "vcpu": 4,
        "ram": 32.0,
        "price_monthly": 96.36,
        "continent": "Asia",
        "country": "Singapore",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-32gb",
        "vcpu": 4,
        "ram": 32.0,
        "price_monthly": 100.74,
        "continent": "Asia",
        "country": "India",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 100.74,
        "continent": "Asia",
        "country": "India",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 105.12,
        "continent": "North America",
        "country": "USA",
    },
    {
        "provider": "DigitalOcean",
        "instance": "s-4vcpu-16gb",
        "vcpu": 4,
        "ram": 16.0,
        "price_monthly": 105.12,
        "continent": "Asia",
        "country": "Singapore",
    },
    {
        "provider": "Hetzner",
        "instance": "CPX41",
        "vcpu": 8,
        "ram": 32.0,
        "price_monthly": 129.89,
        "continent": "Europe",
        "country": "Finland",
    },
]


def _get_fallback_recommendations(
    cpu: int,
    ram: float,
    budget: float,
    region: str,
) -> list[dict]:
    normalized_region = region.strip().lower()
    matches = [
        row
        for row in FALLBACK_CATALOG
        if row["vcpu"] >= cpu
        and row["ram"] >= ram
        and row["price_monthly"] <= budget
        and (
            normalized_region in row["continent"].lower()
            or normalized_region in row["country"].lower()
        )
    ]
    matches.sort(key=lambda row: row["price_monthly"])
    return [
        {
            "provider": row["provider"],
            "instance": row["instance"],
            "vcpu": row["vcpu"],
            "ram": row["ram"],
            "price_monthly": round(row["price_monthly"], 2),
        }
        for row in matches[:3]
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
    except (OSError, SQLAlchemyError):
        # Keep the demo API usable when Postgres is unavailable.
        return _get_fallback_recommendations(
            cpu=cpu,
            ram=ram,
            budget=budget,
            region=region,
        )
