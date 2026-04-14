from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
BRAND_DIR = ROOT / "assets" / "brand"
SOURCE = BRAND_DIR / "logo.png"
MASTER_SIZE = 1024
LOGO_SCALE = 0.8
BACKGROUND_START = (0x6F, 0x19, 0x70)
BACKGROUND_MID = (0xE9, 0x34, 0x8A)
BACKGROUND_END = (0x85, 0x22, 0x7E)
LOGO_COLOR = (255, 255, 255, 255)
ROUNDING = 228
TARGETS = {
    "favicon-16-v2.png": 16,
    "favicon-32-v2.png": 32,
    "favicon-48-v2.png": 48,
    "apple-touch-icon-v2.png": 180,
    "favicon-192-v2.png": 192,
    "favicon-512-v2.png": 512,
}


def blend(color_a: tuple[int, int, int], color_b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(
        round(channel_a + ((channel_b - channel_a) * amount))
        for channel_a, channel_b in zip(color_a, color_b)
    )


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - (2.0 * value))


def build_background(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for x in range(size):
        t = x / (size - 1)
        if t < 0.58:
            base = blend(BACKGROUND_START, BACKGROUND_MID, smoothstep(t / 0.58))
        else:
            base = blend(BACKGROUND_MID, BACKGROUND_END, smoothstep((t - 0.58) / 0.42))
        draw.line((x, 0, x, size), fill=base + (255,))

    highlights = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlights)
    hdraw.ellipse(
        (
            int(size * 0.12),
            int(size * 0.12),
            int(size * 0.82),
            int(size * 0.78),
        ),
        fill=(255, 255, 255, 34),
    )
    hdraw.ellipse(
        (
            int(size * 0.26),
            int(size * 0.06),
            int(size * 0.96),
            int(size * 0.62),
        ),
        fill=(255, 255, 255, 22),
    )
    highlights = highlights.filter(ImageFilter.GaussianBlur(radius=size * 0.045))
    image.alpha_composite(highlights)

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle((0, 0, size - 1, size - 1), radius=ROUNDING, fill=255)
    image.putalpha(mask)
    return image


def build_mask(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    inverted = ImageOps.invert(gray)
    boosted = ImageOps.autocontrast(inverted, cutoff=1)
    return boosted.point(lambda value: 0 if value < 10 else value)


def extract_centered_logo_mask(image: Image.Image) -> Image.Image:
    mask = build_mask(image)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError("Unable to isolate logo from source image.")

    cropped = mask.crop(bbox)
    width, height = cropped.size
    side = max(width, height)
    square = Image.new("L", (side, side), 0)
    offset = ((side - width) // 2, (side - height) // 2)
    square.paste(cropped, offset)
    return square


def build_logo_layer(size: int) -> Image.Image:
    with Image.open(SOURCE) as image:
        logo_mask = extract_centered_logo_mask(image)

    logo_size = int(size * LOGO_SCALE)
    logo_mask = logo_mask.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    logo_mask = logo_mask.filter(ImageFilter.MaxFilter(7))
    logo_mask = logo_mask.filter(ImageFilter.GaussianBlur(radius=0.8))
    logo_mask = ImageOps.autocontrast(logo_mask)

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    logo = Image.new("RGBA", (logo_size, logo_size), LOGO_COLOR)
    logo.putalpha(logo_mask)
    offset = ((size - logo_size) // 2, (size - logo_size) // 2)
    layer.alpha_composite(logo, offset)
    return layer


def export_outputs(master: Image.Image) -> None:
    for filename, size in TARGETS.items():
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        if size <= 48:
            resized = resized.filter(ImageFilter.UnsharpMask(radius=0.9, percent=180, threshold=2))
        resized.save(BRAND_DIR / filename)

    master.save(BRAND_DIR / "favicon-master-v2.png")
    master.save(
        ROOT / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    background = build_background(MASTER_SIZE)
    logo = build_logo_layer(MASTER_SIZE)
    background.alpha_composite(logo)
    export_outputs(background)


if __name__ == "__main__":
    main()
