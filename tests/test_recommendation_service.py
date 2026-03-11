import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.recommendation_service import get_recommendations


class RecommendationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_empty_list_when_database_connection_is_refused(self) -> None:
        session = SimpleNamespace(
            execute=AsyncMock(side_effect=ConnectionRefusedError(111, "Connection refused"))
        )

        recommendations = await get_recommendations(
            session=session,
            cpu=4,
            ram=16.0,
            budget=100.0,
            region="Europe",
        )

        self.assertEqual(recommendations, [])

    async def test_serializes_rows_when_query_succeeds(self) -> None:
        row = SimpleNamespace(
            name="DigitalOcean",
            instance_name="s-4vcpu-16gb",
            vcpu=4,
            ram_gb=16.0,
            monthly_price_usd=96.36,
        )
        session = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [row]))
        )

        recommendations = await get_recommendations(
            session=session,
            cpu=4,
            ram=16.0,
            budget=100.0,
            region="Europe",
        )

        self.assertEqual(
            recommendations,
            [
                {
                    "provider": "DigitalOcean",
                    "instance": "s-4vcpu-16gb",
                    "vcpu": 4,
                    "ram": 16.0,
                    "price_monthly": 96.36,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
