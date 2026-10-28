from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = BASE_DIR / "pic" / "动作差分"
OUTPUT_DIR = BASE_DIR / "pic" / "gif"
CANVAS_SIZE = 512
SPRITE_LIMIT = 464
TRANSPARENT_INDEX = 255


@dataclass(frozen=True)
class MotionSpec:
    frames: int
    duration_ms: int
    motion: str


SPECS: dict[str, MotionSpec] = {
    "00": MotionSpec(12, 110, "idle"),
    "01": MotionSpec(12, 90, "wave"),
    "02": MotionSpec(10, 130, "work"),
    "03": MotionSpec(10, 105, "eat"),
    "04": MotionSpec(14, 150, "sleep"),
    "05": MotionSpec(12, 85, "victory"),
    "06": MotionSpec(12, 105, "pat"),
}


def load_sprite(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError(f"Image has no visible pixels: {path}")
    image = image.crop(alpha_box)
    ratio = min(SPRITE_LIMIT / image.width, SPRITE_LIMIT / image.height)
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    return resize_rgba(image, size)


def resize_rgba(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """在预乘 Alpha 空间缩放，避免透明像素的颜色渗入角色边缘。"""
    return image.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")


def motion_values(kind: str, phase: float) -> tuple[float, float, float, int, int]:
    sine = math.sin(phase)
    pulse = (sine + 1.0) / 2.0

    if kind == "idle":
        # 常态只做一像素左右的轻微悬浮，不持续缩放角色。
        return 1.0, 1.0, 0.0, 0, round(-1.4 * sine)
    if kind == "wave":
        return 1.0, 1.0, 1.2 * sine, round(2 * sine), round(-2 * pulse)
    if kind == "work":
        return 1.0 - 0.003 * sine, 1.0 + 0.005 * sine, 0.0, 0, round(-sine)
    if kind == "eat":
        nibble = abs(math.sin(phase * 2.0))
        return 1.0 + 0.008 * nibble, 1.0 - 0.005 * nibble, 0.0, 0, round(-3 * nibble)
    if kind == "sleep":
        return 1.0 + 0.012 * sine, 1.0 + 0.008 * sine, 0.0, 0, 0
    if kind == "victory":
        jump = max(0.0, sine)
        return 1.0 - 0.018 * jump, 1.0 + 0.025 * jump, 0.0, 0, round(-11 * jump)
    if kind == "pat":
        press = max(0.0, sine)
        return 1.0 + 0.012 * press, 1.0 - 0.025 * press, 0.0, 0, round(4 * press)
    raise ValueError(f"Unknown motion kind: {kind}")


def render_frame(sprite: Image.Image, kind: str, phase: float) -> Image.Image:
    scale_x, scale_y, angle, dx, dy = motion_values(kind, phase)
    width = max(1, round(sprite.width * scale_x))
    height = max(1, round(sprite.height * scale_y))
    transformed = resize_rgba(sprite, (width, height))
    if angle:
        transformed = (
            transformed.convert("RGBa")
            .rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
            .convert("RGBA")
        )

    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    x = (CANVAS_SIZE - transformed.width) // 2 + dx
    if kind == "sleep":
        y = (CANVAS_SIZE - transformed.height) // 2 + dy
    else:
        y = CANVAS_SIZE - transformed.height - 10 + dy
    canvas.alpha_composite(transformed, (x, y))
    return canvas


def gif_frames(frames: list[Image.Image]) -> list[Image.Image]:
    palette = frames[0].convert("RGB").quantize(
        colors=255,
        method=Image.Quantize.MEDIANCUT,
    )
    converted: list[Image.Image] = []

    for frame in frames:
        indexed = frame.convert("RGB").quantize(
            palette=palette,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        transparent_mask = frame.getchannel("A").point(
            lambda alpha: 255 if alpha <= 8 else 0
        )
        indexed.paste(TRANSPARENT_INDEX, mask=transparent_mask)
        indexed.info["transparency"] = TRANSPARENT_INDEX
        indexed.info["disposal"] = 2
        converted.append(indexed)

    return converted


def animate(source: Path, spec: MotionSpec) -> tuple[Path, Path, Path]:
    sprite = load_sprite(source)
    frames = [
        render_frame(sprite, spec.motion, math.tau * index / spec.frames)
        for index in range(spec.frames)
    ]
    indexed = gif_frames(frames)

    gif_path = OUTPUT_DIR / f"{source.stem}.gif"
    indexed[0].save(
        gif_path,
        save_all=True,
        append_images=indexed[1:],
        loop=0,
        duration=spec.duration_ms,
        disposal=2,
        transparency=TRANSPARENT_INDEX,
        optimize=False,
    )

    webp_path = OUTPUT_DIR / f"{source.stem}.webp"
    frames[0].save(
        webp_path,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=spec.duration_ms,
        lossless=True,
        method=6,
    )

    # 桌宠运行时优先使用 APNG：保留完整 8 位 Alpha，边缘比 GIF 更干净。
    apng_path = OUTPUT_DIR / f"{source.stem}.apng"
    frames[0].save(
        apng_path,
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=spec.duration_ms,
        # 每帧结束后清空其区域，避免位移/缩放动作在部分播放器中残影。
        disposal=1,
        blend=0,
        optimize=False,
    )
    return gif_path, webp_path, apng_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCE_DIR.glob("*.png"))
    if not sources:
        raise SystemExit(f"No PNG files found in {SOURCE_DIR}")

    for source in sources:
        prefix = source.name.split("_", 1)[0]
        spec = SPECS.get(prefix)
        if spec is None:
            print(f"skip: {source.name} (no motion spec)")
            continue
        gif_path, webp_path, apng_path = animate(source, spec)
        print(f"created: {gif_path.name}, {webp_path.name}, {apng_path.name}")


if __name__ == "__main__":
    main()
