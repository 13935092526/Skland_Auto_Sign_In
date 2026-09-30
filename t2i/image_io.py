"""图片落盘：模板渲染结果统一由此保存（PNG 直存，JPG/BMP 自动转 RGB 白底）。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def save(img: Image.Image, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = path.suffix.lower()
    if fmt in (".jpg", ".jpeg", ".bmp"):
        if img.mode == "RGBA":
            base = Image.new("RGB", img.size, (255, 255, 255))
            base.paste(img, mask=img.split()[3])
            img_to_save = base
        else:
            img_to_save = img
        img_to_save.save(path, quality=92)
    else:
        img.save(path)
    return path
