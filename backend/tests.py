import os
import unittest
from fastapi.testclient import TestClient
from database import Base

os.environ.setdefault("ALLOW_REGISTRATION", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_nexus_unit.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

import main

class BackendApiTests(unittest.TestCase):
    def setUp(self):
        db_path = "test_nexus_unit.db"
        Base.metadata.drop_all(bind=main.engine)
        Base.metadata.create_all(bind=main.engine)
        self.client = TestClient(main.app)
        r = self.client.post("/auth/register", params={"email": "admin@test.com", "password": "secret123", "tenant_name": "T1"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/auth/login", data={"username": "admin@test.com", "password": "secret123"})
        self.token = r.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        main.engine.dispose()
        if os.path.exists("test_nexus_unit.db"):
            try:
                os.remove("test_nexus_unit.db")
            except PermissionError:
                pass

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_tenant_isolation(self):
        self.client.post("/leads", json={"name": "LeadA"}, headers=self.headers)
        # second tenant
        self.client.post("/auth/register", params={"email": "other@test.com", "password": "secret123", "tenant_name": "T2"})
        r = self.client.post("/auth/login", data={"username": "other@test.com", "password": "secret123"})
        other_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = self.client.get("/leads", headers=other_headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 0)

    def test_lead_crud(self):
        r = self.client.post("/leads", json={"name": "LeadX"}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        lead_id = r.json()["id"]
        r = self.client.get("/leads", headers=self.headers)
        self.assertTrue(any(l["id"] == lead_id for l in r.json()))
        r = self.client.delete(f"/leads/{lead_id}", headers=self.headers)
        self.assertEqual(r.status_code, 200)

    def test_workspace_and_memory(self):
        r = self.client.get("/workspace/summary", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn("leads", r.json())
        r = self.client.post("/memory", json={"lesson": "test lesson"}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/memory", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 1)

if __name__ == "__main__":
    unittest.main()
