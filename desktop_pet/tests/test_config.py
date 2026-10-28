import json
from pathlib import Path
import sys
import unittest


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from app import load_config  # noqa: E402


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = APP_DIR / "tests" / "runtime_data" / "config"
        self.root.mkdir(parents=True, exist_ok=True)
        self.local = self.root / "local.json"

    def tearDown(self) -> None:
        self.local.unlink(missing_ok=True)

    def test_clean_checkout_uses_template_without_writing_personal_config(self) -> None:
        config = load_config(self.local, APP_DIR / "config.example.json")
        self.assertEqual(config["size"], 512)
        self.assertNotIn("x", config)
        self.assertNotIn("y", config)
        self.assertEqual(config["event_countdown"], {"enabled": False})
        self.assertFalse(self.local.exists())

    def test_existing_local_config_takes_precedence(self) -> None:
        self.local.write_text(json.dumps({"size": 320}), encoding="utf-8")
        self.assertEqual(load_config(self.local, APP_DIR / "config.example.json"), {"size": 320})

    def test_non_object_config_is_rejected(self) -> None:
        self.local.write_text("[]", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(self.local, APP_DIR / "config.example.json")
