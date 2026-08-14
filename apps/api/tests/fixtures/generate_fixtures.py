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


def build_oversized_document(path: Path) -> None:
    size = (4100, 40)
    psd = PSDImage.new("RGBA", size, (18, 24, 32, 255))
    layer = psd.create_pixel_layer(
        Image.new("RGBA", size, (60, 120, 220, 255)),
        name="Oversized",
        top=0,
        left=0,
    )
    psd.append(layer)
    psd.save(path)


def build_raster(path: Path, *, image_format: str, size: tuple[int, int], mode: str = "RGBA") -> None:
    image = Image.new(mode, size, (30, 80, 140, 255) if mode == "RGBA" else (30, 80, 140))
    if mode == "RGBA":
        pixels = image.load()
        for x in range(max(1, size[0] // 4)):
            for y in range(max(1, size[1] // 4)):
                pixels[x, y] = (240, 80, 40, 0)
    image.save(path, format=image_format)


def build_svg(path: Path) -> None:
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="16">'
        '<rect width="24" height="16" fill="#1e508c"/></svg>\n',
        encoding="utf-8",
    )


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    build_document(output_dir / "basic.psd", psb=False)
    build_document(output_dir / "basic.psb", psb=True)
    build_oversized_document(output_dir / "oversized.psd")
    build_raster(output_dir / "sample.jpg", image_format="JPEG", size=(12, 8), mode="RGB")
    build_raster(output_dir / "sample.webp", image_format="WEBP", size=(12, 8))
    build_raster(output_dir / "transparent.png", image_format="PNG", size=(16, 16))
    build_raster(output_dir / "low-resolution.png", image_format="PNG", size=(2, 2))
    build_svg(output_dir / "sample.svg")
    (output_dir / "malformed.psd").write_bytes(b"8BPS\x00\x01" + b"\x00" * 128)


if __name__ == "__main__":
    main()
