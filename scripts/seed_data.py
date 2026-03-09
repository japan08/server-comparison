"""
Seed sample providers, regions, instance types, and pricing for testing POST /recommend.
Run from project root: PYTHONPATH=. python scripts/seed_data.py
Supports Europe, USA, Asia, India. Run again to add USA/Asia/India if you only had Europe.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.database as database_module
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InstancePricing, InstanceType, Provider, Region


def _permission_help() -> None:
    print("\nPermission denied: the DB user needs table privileges. As postgres superuser, run:")
    print("  psql -U postgres -d cloud_compare -c \"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_bug_agent;\"")
    print("(Replace ai_bug_agent with the user in your DATABASE_URL if different.)\n")


async def seed() -> None:
    await database_module.initialize_database()
    if database_module.async_session_factory is None:
        raise RuntimeError("Database session factory was not initialized")

    try:
        async with database_module.async_session_factory() as session:
            existing = await session.execute(select(Provider.id).limit(1))
            if existing.scalar_one_or_none() is None:
                await _seed_initial(session)
            else:
                await _seed_more_regions(session)
                await _seed_larger_instances(session)
    except ProgrammingError as e:
        err = str(e).lower()
        if "permission denied" in err or "insufficientprivilege" in err:
            _permission_help()
        raise
    finally:
        await database_module.close_database()


async def _seed_initial(session: AsyncSession) -> None:
    p1 = Provider(name="DigitalOcean", slug="digitalocean", website="https://digitalocean.com")
    p2 = Provider(name="Hetzner", slug="hetzner", website="https://hetzner.com")
    session.add_all([p1, p2])
    await session.flush()

    regions = [
        Region(provider_id=p1.id, region_code="fra1", region_name="Frankfurt", country="Germany", continent="Europe"),
        Region(provider_id=p2.id, region_code="fsn1", region_name="Falkenstein", country="Germany", continent="Europe"),
        Region(provider_id=p1.id, region_code="sfo3", region_name="San Francisco", country="USA", continent="North America"),
        Region(provider_id=p2.id, region_code="hel1", region_name="Helsinki", country="Finland", continent="Europe"),
        Region(provider_id=p1.id, region_code="sgp1", region_name="Singapore", country="Singapore", continent="Asia"),
        Region(provider_id=p1.id, region_code="blr1", region_name="Bangalore", country="India", continent="Asia"),
    ]
    session.add_all(regions)
    await session.flush()
    r_eu1, r_eu2, r_usa, r_eu3, r_asia, r_india = regions

    i1 = InstanceType(
        provider_id=p1.id,
        instance_name="s-4vcpu-16gb",
        family="general",
        vcpu=4,
        ram_gb=16.0,
        storage_type="ssd",
        storage_gb=320.0,
        network_performance="standard",
        is_active=True,
    )
    i2 = InstanceType(
        provider_id=p2.id,
        instance_name="CPX31",
        family="cloud",
        vcpu=4,
        ram_gb=16.0,
        storage_type="nvme",
        storage_gb=160.0,
        network_performance="20 Gbit",
        is_active=True,
    )
    i3 = InstanceType(
        provider_id=p1.id,
        instance_name="s-4vcpu-32gb",
        family="general",
        vcpu=4,
        ram_gb=32.0,
        storage_type="ssd",
        storage_gb=640.0,
        network_performance="standard",
        is_active=True,
    )
    i4 = InstanceType(
        provider_id=p2.id,
        instance_name="CPX41",
        family="cloud",
        vcpu=8,
        ram_gb=32.0,
        storage_type="nvme",
        storage_gb=240.0,
        network_performance="20 Gbit",
        is_active=True,
    )
    session.add_all([i1, i2, i3, i4])
    await session.flush()

    session.add_all([
        InstancePricing(instance_type_id=i1.id, region_id=r_eu1.id, pricing_model="on_demand", hourly_price_usd=0.132, monthly_price_usd=96.36, currency="USD"),
        InstancePricing(instance_type_id=i2.id, region_id=r_eu2.id, pricing_model="on_demand", hourly_price_usd=0.089, monthly_price_usd=64.97, currency="USD"),
        InstancePricing(instance_type_id=i1.id, region_id=r_usa.id, pricing_model="on_demand", hourly_price_usd=0.144, monthly_price_usd=105.12, currency="USD"),
        InstancePricing(instance_type_id=i1.id, region_id=r_asia.id, pricing_model="on_demand", hourly_price_usd=0.144, monthly_price_usd=105.12, currency="USD"),
        InstancePricing(instance_type_id=i1.id, region_id=r_india.id, pricing_model="on_demand", hourly_price_usd=0.138, monthly_price_usd=100.74, currency="USD"),
        # Larger instances (>= 30 GB RAM) for Asia / India (prices within $100 budget for testing)
        InstancePricing(instance_type_id=i3.id, region_id=r_asia.id, pricing_model="on_demand", hourly_price_usd=0.132, monthly_price_usd=96.36, currency="USD"),
        InstancePricing(instance_type_id=i3.id, region_id=r_india.id, pricing_model="on_demand", hourly_price_usd=0.138, monthly_price_usd=100.74, currency="USD"),
        InstancePricing(instance_type_id=i4.id, region_id=r_eu2.id, pricing_model="on_demand", hourly_price_usd=0.178, monthly_price_usd=129.89, currency="USD"),
    ])
    await session.commit()
    print("Seed data inserted: 2 providers, 6 regions (Europe, USA, Asia, India), 4 instance types, 8 pricing rows.")


async def _seed_more_regions(session: AsyncSession) -> None:
    has_usa = await session.execute(select(Region.id).where(Region.country.ilike("%USA%")).limit(1))
    if has_usa.scalar_one_or_none() is not None:
        print("USA/Asia/India regions already present, skipping.")
        return

    providers = (await session.execute(select(Provider).order_by(Provider.id))).scalars().all()
    instance_types = (await session.execute(select(InstanceType).order_by(InstanceType.id))).scalars().all()
    if len(providers) < 2 or len(instance_types) < 2:
        print("Need at least 2 providers and 2 instance types; run full seed first.")
        return

    p1, p2 = providers[0], providers[1]
    i1, i2 = instance_types[0], instance_types[1]

    new_regions = [
        Region(provider_id=p1.id, region_code="sfo3", region_name="San Francisco", country="USA", continent="North America"),
        Region(provider_id=p1.id, region_code="sgp1", region_name="Singapore", country="Singapore", continent="Asia"),
        Region(provider_id=p1.id, region_code="blr1", region_name="Bangalore", country="India", continent="Asia"),
    ]
    session.add_all(new_regions)
    await session.flush()

    for r in new_regions:
        session.add(InstancePricing(instance_type_id=i1.id, region_id=r.id, pricing_model="on_demand", hourly_price_usd=0.14, monthly_price_usd=102.20, currency="USD"))
    await session.commit()
    print("Added 3 regions (USA, Asia, India) and pricing. You can now query by USA, Asia, India.")


async def _seed_larger_instances(session: AsyncSession) -> None:
    """Add instance types with >= 30 GB RAM if missing (so 30 GB requests return results)."""
    from sqlalchemy import func

    has_large = await session.execute(
        select(InstanceType.id).where(InstanceType.ram_gb >= 30).limit(1)
    )
    if has_large.scalar_one_or_none() is not None:
        return

    providers = (await session.execute(select(Provider).order_by(Provider.id))).scalars().all()
    if len(providers) < 2:
        return

    regions = (
        await session.execute(
            select(Region).where(
                func.coalesce(Region.continent, "").ilike("%Asia%")
            ).limit(2)
        )
    ).scalars().all()
    if not regions:
        regions = (await session.execute(select(Region).limit(2))).scalars().all()
    if not regions:
        return

    p1, p2 = providers[0], providers[1]
    r_asia = regions[0]
    r_other = regions[1] if len(regions) > 1 else regions[0]

    i3 = InstanceType(
        provider_id=p1.id,
        instance_name="s-4vcpu-32gb",
        family="general",
        vcpu=4,
        ram_gb=32.0,
        storage_type="ssd",
        storage_gb=640.0,
        network_performance="standard",
        is_active=True,
    )
    i4 = InstanceType(
        provider_id=p2.id,
        instance_name="CPX41",
        family="cloud",
        vcpu=8,
        ram_gb=32.0,
        storage_type="nvme",
        storage_gb=240.0,
        network_performance="20 Gbit",
        is_active=True,
    )
    session.add_all([i3, i4])
    await session.flush()

    session.add_all([
        InstancePricing(instance_type_id=i3.id, region_id=r_asia.id, pricing_model="on_demand", hourly_price_usd=0.132, monthly_price_usd=96.36, currency="USD"),
        InstancePricing(instance_type_id=i3.id, region_id=r_other.id, pricing_model="on_demand", hourly_price_usd=0.138, monthly_price_usd=100.74, currency="USD"),
        InstancePricing(instance_type_id=i4.id, region_id=r_other.id, pricing_model="on_demand", hourly_price_usd=0.178, monthly_price_usd=129.89, currency="USD"),
    ])
    await session.commit()
    print("Added 2 larger instance types (4vCPU/32GB, 8vCPU/32GB) and pricing. Queries for 30+ GB RAM will now return results.")


if __name__ == "__main__":
    asyncio.run(seed())
