from PIL import Image
import pytest

from modules.canvas_processor import CanvasOptions, normalize_hex_color, process_canvas


@pytest.mark.parametrize(
    ("value", "expected"),
    [("#FFFFFF", "#FFFFFF"), ("FFFFFF", "#FFFFFF"), ("#FFF", "#FFFFFF"), ("fff", "#FFFFFF")],
)
def test_hex_normalization(value: str, expected: str) -> None:
    assert normalize_hex_color(value) == expected


def test_invalid_hex() -> None:
    with pytest.raises(ValueError, match="Invalid HEX"):
        normalize_hex_color("#GG00XX")


def test_square_canvas_padding_center_and_no_upscale() -> None:
    source = Image.new("RGBA", (100, 50), (255, 0, 0, 128))
    result = process_canvas(
        source, CanvasOptions(canvas_mode="Square canvas", square_side=400, padding=10, padding_unit="%", allow_upscaling=False)
    )
    assert result.size == (400, 400)
    assert result.getpixel((200, 200))[3] == 255
    assert result.getpixel((10, 10))[:3] == (255, 255, 255)


def test_percent_padding_uses_smaller_side_and_preserves_ratio() -> None:
    source = Image.new("RGBA", (1000, 500), "red")
    result = process_canvas(
        source,
        CanvasOptions(canvas_mode="Custom size", width=1000, height=1200, padding=10, padding_unit="%", allow_upscaling=True),
    )
    assert result.size == (1000, 1200)
    # Available width is 800 after 100 px on each side; a 2:1 object becomes 800x400.
    assert result.getpixel((99, 600))[:3] == (255, 255, 255)
    assert result.getpixel((100, 600))[:3] == (255, 0, 0)


def test_transparent_background_and_crop() -> None:
    source = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(30, 70):
        for y in range(40, 60):
            source.putpixel((x, y), (0, 120, 255, 128))
    result = process_canvas(
        source, CanvasOptions(transparent=True, canvas_mode="Custom size", width=200, height=200, padding=0)
    )
    assert result.getpixel((0, 0))[3] == 0
    assert 0 < result.getpixel((100, 100))[3] < 255


def test_fully_transparent_is_rejected() -> None:
    with pytest.raises(ValueError, match="fully transparent"):
        process_canvas(Image.new("RGBA", (20, 20), (0, 0, 0, 0)), CanvasOptions())


def test_background_image_is_used(tmp_path) -> None:
    background = tmp_path / "background.png"
    Image.new("RGB", (60, 60), "blue").save(background)
    result = process_canvas(
        Image.new("RGBA", (10, 10), (255, 0, 0, 255)),
        CanvasOptions(canvas_mode="Square canvas", square_side=100, background_image=str(background)),
    )
    assert result.getpixel((0, 0))[:3] == (0, 0, 255)
