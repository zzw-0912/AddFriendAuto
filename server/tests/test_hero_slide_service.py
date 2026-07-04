import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.models.hero_slide import HeroSlide  # noqa: F401
from app.services import hero_slide_service


class HeroSlideServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()
        self.temp_dir = tempfile.TemporaryDirectory()
        hero_slide_service.HERO_SLIDE_UPLOAD_DIR = Path(self.temp_dir.name) / "hero-slides"

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def upload_file(self, name: str, content: bytes, content_type: str = "image/png") -> UploadFile:
        return UploadFile(file=BytesIO(content), filename=name, size=len(content), headers=None)

    def test_list_hero_slides_returns_three_empty_slots_by_default(self):
        result = hero_slide_service.list_hero_slides(self.db)

        self.assertEqual([item.slot_index for item in result], [1, 2, 3])
        self.assertTrue(all(item.image_url is None for item in result))

    def test_upload_exposes_image_url_for_slot(self):
        image = self.upload_file("slide-one.png", b"image-one")

        saved = hero_slide_service.upload_hero_slide_image(1, image, self.db)
        listed = hero_slide_service.list_hero_slides(self.db)

        self.assertIsNotNone(saved.image_url)
        self.assertTrue(saved.image_url.startswith("/uploads/hero-slides/1/"))
        self.assertEqual(listed[0].image_url, saved.image_url)
        self.assertTrue((hero_slide_service.HERO_SLIDE_UPLOAD_DIR / "1" / Path(saved.image_url).name).exists())

    def test_replace_same_slot_removes_old_file(self):
        first = hero_slide_service.upload_hero_slide_image(2, self.upload_file("first.png", b"first"), self.db)
        old_file = hero_slide_service.HERO_SLIDE_UPLOAD_DIR / "2" / Path(first.image_url or "").name

        second = hero_slide_service.upload_hero_slide_image(2, self.upload_file("second.png", b"second"), self.db)
        new_file = hero_slide_service.HERO_SLIDE_UPLOAD_DIR / "2" / Path(second.image_url or "").name

        self.assertNotEqual(first.image_url, second.image_url)
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())

    def test_clear_slot_removes_image_and_resets_path(self):
        saved = hero_slide_service.upload_hero_slide_image(3, self.upload_file("third.webp", b"third", "image/webp"), self.db)
        file_path = hero_slide_service.HERO_SLIDE_UPLOAD_DIR / "3" / Path(saved.image_url or "").name

        cleared = hero_slide_service.clear_hero_slide_image(3, self.db)

        self.assertIsNone(cleared.image_url)
        self.assertFalse(file_path.exists())

    def test_invalid_extension_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            hero_slide_service.upload_hero_slide_image(1, self.upload_file("bad.gif", b"gif"), self.db)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Only jpg, jpeg, png, webp images are supported")


if __name__ == "__main__":
    unittest.main()
