"""Pure Pillow canvas composition used by preview and batch processing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image, ImageOps


HEX_PATTERN = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex_color(value: str) -> str:
    match = HEX_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError("Invalid HEX color. Use #RRGGBB, for example #FFFFFF")
    digits = match.group(1).upper()
    if len(digits) == 3:
        digits = "".join(character * 2 for character in digits)
    return f"#{digits}"


@dataclass(frozen=True)
class CanvasOptions:
    background_color: str = "#FFFFFF"
    transparent: bool = False
    canvas_mode: str = "Keep original size"
    width: int = 1000
    height: int = 1000
    square_side: int = 1000
    padding: float = 10
    padding_unit: str = "%"
    crop_transparent: bool = True
    preserve_aspect: bool = True
    center: bool = True
    allow_upscaling: bool = False
    background_image: str = ""


def _canvas_size(original: tuple[int, int], options: CanvasOptions) -> tuple[int, int]:
    if options.canvas_mode == "Keep original size":
        size = original
    elif options.canvas_mode == "Square canvas":
        size = (options.square_side, options.square_side)
    elif options.canvas_mode == "Custom size":
        size = (options.width, options.height)
    else:
        raise ValueError(f"Unknown canvas mode: {options.canvas_mode}")
    if min(size) < 16:
        raise ValueError("Canvas dimensions must be at least 16 px")
    if max(size) > 12000 or size[0] * size[1] > 80_000_000:
        raise ValueError("Canvas is too large; maximum is 12000 px per side and 80 megapixels")
    return size


def _padding_px(canvas_size: tuple[int, int], value: float, unit: str) -> int:
    if value < 0:
        raise ValueError("Padding cannot be negative")
    if unit == "%":
        if value >= 50:
            raise ValueError("Padding percentage must be less than 50%")
        return round(min(canvas_size) * value / 100)
    if unit == "px":
        return round(value)
    raise ValueError("Padding unit must be px or %")


def process_canvas(source: Image.Image, options: CanvasOptions) -> Image.Image:
    """Compose an image on a validated canvas without modifying the source."""
    oriented = ImageOps.exif_transpose(source)
    original_size = oriented.size
    rgba = oriented.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("The image is fully transparent")
    if options.crop_transparent:
        rgba = rgba.crop(bbox)

    canvas_size = _canvas_size(original_size, options)
    padding = _padding_px(canvas_size, options.padding, options.padding_unit)
    available = (canvas_size[0] - 2 * padding, canvas_size[1] - 2 * padding)
    if min(available) <= 0:
        raise ValueError("Padding leaves no usable canvas area")

    if options.preserve_aspect:
        scale = min(available[0] / rgba.width, available[1] / rgba.height)
        if not options.allow_upscaling:
            scale = min(scale, 1.0)
        target_size = (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale)))
    else:
        target_size = available
        if not options.allow_upscaling:
            target_size = (min(target_size[0], rgba.width), min(target_size[1], rgba.height))
    if target_size != rgba.size:
        rgba = rgba.resize(target_size, Image.Resampling.LANCZOS)

    if options.transparent:
        canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    elif options.background_image:
        try:
            with Image.open(options.background_image) as background_source:
                background = ImageOps.exif_transpose(background_source).convert("RGBA")
                canvas = ImageOps.fit(background, canvas_size, Image.Resampling.LANCZOS)
        except OSError as exc:
            raise ValueError(f"Background image could not be opened: {exc}") from exc
    else:
        color = normalize_hex_color(options.background_color)
        canvas = Image.new("RGBA", canvas_size, color)
    position = (
        (canvas_size[0] - rgba.width) // 2 if options.center else padding,
        (canvas_size[1] - rgba.height) // 2 if options.center else padding,
    )
    canvas.alpha_composite(rgba, position)
    return canvas
