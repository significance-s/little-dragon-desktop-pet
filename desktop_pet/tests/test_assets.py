from pathlib import Path
import sys
import unittest

from PIL import Image, ImageSequence


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

from pet.assets import AssetCatalog, STATE_FILES  # noqa: E402
from pet.tray import make_tray_image  # noqa: E402
from pet.window import (  # noqa: E402
    MAX_SIZE,
    MIN_SIZE,
    clamp_size,
    prepare_frame_for_window,
    study_panel_position,
)


class AssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = AssetCatalog.discover(PROJECT_DIR / "pic" / "gif")

    def test_every_state_has_an_asset(self) -> None:
        self.assertEqual(set(self.catalog.files), set(STATE_FILES))

    def test_animations_are_valid(self) -> None:
        self.catalog.validate()

    def test_runtime_assets_keep_smooth_alpha_edges(self) -> None:
        with Image.open(self.catalog.files["idle"]) as image:
            alpha_histogram = image.convert("RGBA").getchannel("A").histogram()
        self.assertGreater(sum(alpha_histogram[1:255]), 0)

    def test_size_is_clamped_to_supported_range(self) -> None:
        self.assertEqual(clamp_size(1), MIN_SIZE)
        self.assertEqual(clamp_size(260), 260)
        self.assertEqual(clamp_size(9999), MAX_SIZE)

    def test_color_key_frame_erases_transparent_pixels(self) -> None:
        source = Image.new("RGBA", (2, 1), (255, 255, 255, 255))
        source.putpixel((0, 0), (255, 0, 255, 0))
        prepared = prepare_frame_for_window(source, 2, "#010203", True)
        self.assertEqual(prepared.mode, "RGB")
        self.assertEqual(prepared.getpixel((0, 0)), (1, 2, 3))
        self.assertEqual(prepared.getpixel((1, 0)), (255, 255, 255))

    def test_study_panel_docks_on_screen(self) -> None:
        self.assertEqual(study_panel_position(100, 100, 260, 1920, 1080), (370, 122))
        panel_x, panel_y = study_panel_position(1750, 900, 260, 1920, 1080)
        self.assertEqual(panel_x, 1420)
        self.assertLessEqual(panel_y + 215, 1080)

    def test_tray_icon_is_rendered_from_idle_asset(self) -> None:
        icon = make_tray_image(self.catalog.files["idle"])
        self.assertEqual(icon.size, (64, 64))
        self.assertEqual(icon.mode, "RGBA")
        self.assertIsNotNone(icon.getchannel("A").getbbox())

    def test_idle_does_not_scale_but_pet_reaction_does(self) -> None:
        def visible_sizes(path: Path) -> set[tuple[int, int]]:
            sizes: set[tuple[int, int]] = set()
            with Image.open(path) as image:
                for frame in ImageSequence.Iterator(image):
                    bounds = frame.convert("RGBA").getchannel("A").getbbox()
                    self.assertIsNotNone(bounds)
                    assert bounds is not None
                    sizes.add((bounds[2] - bounds[0], bounds[3] - bounds[1]))
            return sizes

        self.assertEqual(len(visible_sizes(self.catalog.files["idle"])), 1)
        self.assertGreater(len(visible_sizes(self.catalog.files["pet"])), 1)


if __name__ == "__main__":
    unittest.main()
