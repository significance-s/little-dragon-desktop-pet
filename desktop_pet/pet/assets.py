from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


STATE_FILES: dict[str, str] = {
    "idle": "00_待机母版.apng",
    "wave": "01_招手.apng",
    "work": "02_工作.apng",
    "eat": "03_吃饭.apng",
    "sleep": "04_睡觉.apng",
    "victory": "05_胜利.apng",
    "pet": "06_摸头反应.apng",
}

STATE_LABELS: dict[str, str] = {
    "idle": "待机",
    "wave": "招手",
    "work": "工作",
    "eat": "吃饭",
    "sleep": "睡觉",
    "victory": "胜利",
    "pet": "摸头",
}


@dataclass(frozen=True)
class AssetCatalog:
    root: Path
    files: dict[str, Path]

    @classmethod
    def discover(cls, root: Path) -> "AssetCatalog":
        files = {state: root / filename for state, filename in STATE_FILES.items()}
        missing = [path for path in files.values() if not path.is_file()]
        if missing:
            rendered = "\n".join(f"- {path}" for path in missing)
            raise FileNotFoundError(f"缺少桌宠动画素材：\n{rendered}")
        return cls(root=root, files=files)

    def validate(self) -> None:
        errors: list[str] = []
        for state, path in self.files.items():
            try:
                with Image.open(path) as image:
                    frame_count = getattr(image, "n_frames", 1)
                    if frame_count < 2:
                        errors.append(f"{state}: 动画少于 2 帧 ({path.name})")
                    if image.size != (512, 512):
                        errors.append(f"{state}: 尺寸应为 512x512，实际为 {image.size}")
                    image.seek(0)
                    alpha = image.convert("RGBA").getchannel("A")
                    if alpha.getextrema()[0] == 255:
                        errors.append(f"{state}: 动画缺少透明区域")
            except OSError as exc:
                errors.append(f"{state}: 无法读取 {path.name}: {exc}")

        if errors:
            raise ValueError("动画素材校验失败：\n" + "\n".join(f"- {e}" for e in errors))
