from __future__ import annotations

from pathlib import Path

from PIL import Image
from psd_tools import PSDImage


def build_document(path: Path, *, psb: bool) -> None:
    psd = PSDImage.new("RGBA", (160, 100), (18, 24, 32, 255))
    background = psd.create_pixel_layer(
        Image.new("RGBA", (160, 100), (45, 55, 68, 255)),
        name="Background",
        top=0,
        left=0,
    )
    group = psd.create_group(name="HUD")
    button = psd.create_pixel_layer(
        Image.new("RGBA", (72, 26), (255, 100, 40, 220)),
        name="Button",
        top=18,
        left=24,
        opacity=230,
    )
    group.append(button)
    psd.append(background)
    psd.append(group)
    if psb:
        psd._record.header.version = 2
    psd.save(path)


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    build_document(output_dir / "basic.psd", psb=False)
    build_document(output_dir / "basic.psb", psb=True)


if __name__ == "__main__":
    main()

