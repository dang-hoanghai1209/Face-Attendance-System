import os
import unittest
from pathlib import Path


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

import main


class StaticMediaTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.media_file = main.MEDIA_DIR / "alerts" / "static-test" / "capture.jpg"
        self.media_file.parent.mkdir(parents=True, exist_ok=True)
        self.media_file.write_bytes(b"test-media-bytes")

    def tearDown(self):
        if self.media_file.exists():
            self.media_file.unlink()
        try:
            self.media_file.parent.rmdir()
        except OSError:
            pass

    def test_media_directory_exists_after_import(self):
        self.assertTrue(main.MEDIA_DIR.exists())
        self.assertTrue(main.MEDIA_DIR.is_dir())

    def test_media_static_route_serves_alert_capture(self):
        response = self.client.get("/media/alerts/static-test/capture.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"test-media-bytes")


if __name__ == "__main__":
    unittest.main()
