import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core import database
from app.core.database import Base
from app.models.client_update import ClientUpdateConfig
from app import main as main_module


if not any(getattr(route, "path", "") == "/version-test-ping" for route in main_module.app.routes):
    @main_module.app.get("/version-test-ping")
    def version_test_ping():
        return {"ok": True}


class ClientUpdateMiddlewareTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.original_main_session = main_module.SessionLocal
        self.original_database_session = database.SessionLocal
        self.original_init_db = main_module.init_db
        main_module.SessionLocal = self.Session
        database.SessionLocal = self.Session
        main_module.init_db = lambda: None
        self.client = TestClient(main_module.app)

    def tearDown(self):
        main_module.SessionLocal = self.original_main_session
        database.SessionLocal = self.original_database_session
        main_module.init_db = self.original_init_db
        self.engine.dispose()

    def set_config(self, *, force: bool, latest_version: str = "9.9.9"):
        db = self.Session()
        try:
            db.merge(
                ClientUpdateConfig(
                    id=1,
                    latest_version=latest_version,
                    force_update_enabled=force,
                    download_url="https://example.com/friendauto.exe",
                    qr_image_path="/uploads/client-update/qr.png",
                    message="请下载最新版本后继续使用。",
                )
            )
            db.commit()
        finally:
            db.close()

    def test_force_update_disabled_allows_request_without_version_header(self):
        self.set_config(force=False, latest_version="9.9.9")

        res = self.client.get("/version-test-ping")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True})

    def test_force_update_enabled_allows_matching_version(self):
        self.set_config(force=True, latest_version="1.2.3")

        res = self.client.get("/version-test-ping", headers={"X-Client-Version": "1.2.3"})

        self.assertEqual(res.status_code, 200)

    def test_force_update_enabled_blocks_missing_version(self):
        self.set_config(force=True, latest_version="1.2.3")

        res = self.client.get("/version-test-ping")

        self.assertEqual(res.status_code, 426)
        self.assertEqual(res.headers.get("X-Required-Client-Version"), "1.2.3")
        body = res.json()
        self.assertEqual(body["code"], "CLIENT_UPDATE_REQUIRED")
        self.assertEqual(body["latest_version"], "1.2.3")
        self.assertEqual(body["download_url"], "https://example.com/friendauto.exe")
        self.assertEqual(body["qr_image_url"], "/uploads/client-update/qr.png")

    def test_force_update_enabled_blocks_mismatched_version(self):
        self.set_config(force=True, latest_version="1.2.3")

        res = self.client.get("/version-test-ping", headers={"X-Client-Version": "1.2.2"})

        self.assertEqual(res.status_code, 426)

    def test_skip_paths_are_not_blocked_by_update_gate(self):
        self.set_config(force=True, latest_version="1.2.3")
        headers = {"X-Client-Version": "0.0.1"}

        health = self.client.get("/health", headers=headers)
        admin = self.client.get("/admin/client-update", headers=headers)
        upload = self.client.get("/uploads/not-found.png", headers=headers)
        config = self.client.get("/client-update/config", headers=headers)

        self.assertEqual(health.status_code, 200)
        self.assertNotEqual(admin.status_code, 426)
        self.assertNotEqual(upload.status_code, 426)
        self.assertEqual(config.status_code, 200)


if __name__ == "__main__":
    unittest.main()
