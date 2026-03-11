import unittest

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


class FailingSession:
    async def execute(self, stmt):
        raise ConnectionRefusedError("[Errno 111] Connection refused")


async def override_get_db():
    yield FailingSession()


class RecommendEndpointTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_recommend_returns_empty_list_when_db_is_unavailable(self):
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.post(
                "/recommend",
                json={"cpu": 4, "ram": 16, "budget": 100, "region": "Europe"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"recommendations": [], "explanation": None},
        )
