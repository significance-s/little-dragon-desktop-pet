from pathlib import Path
import sys
import unittest
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from pet.runtime import runtime_paths  # noqa: E402


class RuntimePathTests(unittest.TestCase):
    def test_source_layout_is_unchanged(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            paths = runtime_paths(source_dir=APP_DIR, frozen=False)
        self.assertEqual(paths.config, APP_DIR / "config.json")
        self.assertEqual(paths.assets, APP_DIR.parent / "pic" / "gif")
        self.assertEqual(paths.template, APP_DIR / "config.example.json")

    def test_frozen_resources_and_writable_state_are_separate(self) -> None:
        bundle, local = Path("bundle"), Path("local-appdata")
        with patch.dict("os.environ", {}, clear=True):
            paths = runtime_paths(frozen=True, bundle_dir=bundle, local_appdata=local)
        self.assertEqual(paths.assets, bundle / "pic" / "gif")
        self.assertEqual(paths.template, bundle / "config.example.json")
        self.assertEqual(paths.config, local / "LittleDragonDesktopPet" / "config.json")
        self.assertNotEqual(paths.state_dir, bundle)

    def test_data_override_never_changes_resource_location(self) -> None:
        paths = runtime_paths(frozen=True, bundle_dir=Path("bundle"), data_dir=Path("qa-state"))
        self.assertEqual(paths.assets, Path("bundle/pic/gif"))
        self.assertEqual(paths.state_dir, Path("qa-state").resolve())
        self.assertEqual(paths.data, paths.state_dir / "data")

    def test_source_bridge_can_target_exe_state_directory(self) -> None:
        paths = runtime_paths(source_dir=APP_DIR, frozen=False, data_dir=Path("exe-state"))
        self.assertEqual(paths.data, Path("exe-state").resolve() / "data")
        self.assertEqual(paths.template, APP_DIR / "config.example.json")


if __name__ == "__main__":
    unittest.main()
