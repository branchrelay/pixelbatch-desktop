from io import BytesIO

from PIL import Image

from modules.image_optimizer import encode_image, optimize_to_max_size, size_to_bytes


def assert_valid(data: bytes) -> None:
    with Image.open(BytesIO(data)) as image:
        image.verify()


def test_jpeg_and_webp_reach_limit() -> None:
    image = Image.effect_noise((256, 256), 80).convert("RGB")
    for fmt in ("JPEG", "WEBP"):
        result = optimize_to_max_size(image, fmt, 25_000, True, min_quality=30)
        assert result.target_reached
        assert result.final_size == len(result.image_bytes) <= 25_000
        assert_valid(result.image_bytes)


def test_png_alpha_is_preserved() -> None:
    image = Image.new("RGBA", (100, 100), (10, 20, 30, 120))
    result = optimize_to_max_size(image, "PNG", 20_000, False)
    assert result.target_reached
    with Image.open(BytesIO(result.image_bytes)) as decoded:
        assert decoded.mode == "RGBA"
        assert decoded.getpixel((0, 0))[3] == 120


def test_unreachable_limit_reports_failure() -> None:
    image = Image.effect_noise((300, 300), 100).convert("RGB")
    result = optimize_to_max_size(image, "JPEG", 10, False, min_quality=60)
    assert not result.target_reached
    assert result.warning


def test_units_and_plain_encoding() -> None:
    assert size_to_bytes(1, "KB") == 1024
    assert size_to_bytes(1, "MB") == 1024 * 1024
    assert_valid(encode_image(Image.new("RGB", (20, 20), "white"), "JPEG"))
    assert_valid(encode_image(Image.new("RGB", (20, 20), "white"), "BMP"))
    assert_valid(encode_image(Image.new("RGB", (20, 20), "white"), "TIFF"))
