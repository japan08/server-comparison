import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core import database
from app.main import app


class RecommendRouteFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        async def override_get_db():
            yield object()

        app.dependency_overrides[database.get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_empty_recommendations_when_database_is_unavailable(self) -> None:
        payload = {
            "cpu": 4,
            "ram": 16,
            "budget": 100,
            "region": "Europe",
            "include_explanation": True,
        }

        with patch(
            "app.api.routes.recommend.get_recommendations",
            new=AsyncMock(side_effect=ConnectionRefusedError("database is down")),
        ), patch(
            "app.api.routes.recommend.generate_explanation",
            new=AsyncMock(),
        ) as generate_explanation:
            response = self.client.post("/recommend", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"recommendations": [], "explanation": None},
        )
        generate_explanation.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
