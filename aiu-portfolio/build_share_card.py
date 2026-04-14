from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
BRAND_DIR = ROOT / "assets" / "brand"
LOGO_PATH = BRAND_DIR / "logo.png"
OUTPUT_WIDTH = 1200
OUTPUT_HEIGHT = 630
RENDER_SCALE = 2
WIDTH = OUTPUT_WIDTH * RENDER_SCALE
HEIGHT = OUTPUT_HEIGHT * RENDER_SCALE
FONT_WORDMARK = Path(r"C:\Windows\Fonts\bahnschrift.ttf")

BG_LEFT = (0x2B, 0x0C, 0x4A)
BG_RIGHT = (0x8A, 0x1F, 0x7D)
MAGENTA_GLOW = (0xE9, 0x38, 0x9A)
VIOLET_GLOW = (0xA4, 0x61, 0xFF)
YELLOW = (0xF2, 0xC7, 0x3A)
WHITE = (255, 255, 255, 255)


def s(value: int | float) -> int:
    return int(round(value * RENDER_SCALE))


def blend(color_a: tuple[int, int, int], color_b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(
        round(channel_a + ((channel_b - channel_a) * amount))
        for channel_a, channel_b in zip(color_a, color_b)
    )


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - (2.0 * value))


def build_background() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    pixels = image.load()

    for y in range(HEIGHT):
        vertical = smoothstep(y / (HEIGHT - 1))
        for x in range(WIDTH):
            horizontal = smoothstep(x / (WIDTH - 1))
            base = blend(BG_LEFT, BG_RIGHT, horizontal * 0.92)
            tone = blend(base, (0x33, 0x12, 0x50), vertical * 0.16)
            pixels[x, y] = tone + (255,)

    return image


def add_glow(canvas: Image.Image, box: tuple[int, int, int, int], color: tuple[int, int, int], alpha: int, blur: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse(box, fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=s(blur)))
    canvas.alpha_composite(layer)


def build_logo_mask() -> Image.Image:
    with Image.open(LOGO_PATH) as image:
        gray = image.convert("L")
        inverted = ImageOps.invert(gray)
        boosted = ImageOps.autocontrast(inverted, cutoff=1)
        mask = boosted.point(lambda value: 0 if value < 8 else value)
        bbox = mask.getbbox()
        if bbox is None:
            raise RuntimeError("Unable to isolate logo.")
        cropped = mask.crop(bbox)
        side = max(cropped.size)
        square = Image.new("L", (side, side), 0)
        offset = ((side - cropped.size[0]) // 2, (side - cropped.size[1]) // 2)
        square.paste(cropped, offset)
        return square


def render_logo(size: int) -> Image.Image:
    mask = build_logo_mask().resize((size, size), Image.Resampling.LANCZOS)
    mask = mask.filter(ImageFilter.MaxFilter(5 if RENDER_SCALE == 1 else 7))
    mask = ImageOps.autocontrast(mask)

    logo = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    soft_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(soft_glow)
    glow_draw.bitmap((0, 0), mask, fill=(255, 255, 255, 48))
    soft_glow = soft_glow.filter(ImageFilter.GaussianBlur(radius=s(9)))
    logo.alpha_composite(soft_glow)

    solid = Image.new("RGBA", (size, size), WHITE)
    solid.putalpha(mask)
    logo.alpha_composite(solid)
    return logo


def add_yellow_accent(canvas: Image.Image) -> None:
    add_glow(canvas, (s(930), s(62), s(1080), s(212)), YELLOW, 92, 34)

    accent = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(accent)
    draw.ellipse((s(987), s(100), s(1017), s(130)), fill=YELLOW + (255,))
    draw.ellipse((s(1036), s(124), s(1050), s(138)), fill=YELLOW + (235,))
    accent = accent.filter(ImageFilter.GaussianBlur(radius=s(0.4)))
    canvas.alpha_composite(accent)


def add_composition(canvas: Image.Image) -> None:
    add_glow(canvas, (s(220), s(70), s(900), s(540)), VIOLET_GLOW, 80, 110)
    add_glow(canvas, (s(350), s(130), s(980), s(520)), MAGENTA_GLOW, 46, 126)
    add_glow(canvas, (s(120), s(420), s(520), s(780)), MAGENTA_GLOW, 28, 120)

    logo = render_logo(s(286))
    canvas.alpha_composite(logo, ((WIDTH - s(286)) // 2, s(128)))

    sheen = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheen)
    draw.rounded_rectangle((s(160), s(74), s(1040), s(566)), radius=s(78), outline=(255, 255, 255, 12), width=s(2))
    sheen = sheen.filter(ImageFilter.GaussianBlur(radius=s(1.2)))
    canvas.alpha_composite(sheen)

    add_wordmark(canvas)


def add_wordmark(canvas: Image.Image) -> None:
    wordmark = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(wordmark)
    font = ImageFont.truetype(str(FONT_WORDMARK), s(86))
    tracking = s(24)
    baseline_y = s(428)
    letters = list("AIU")
    widths: list[int] = []

    for letter in letters:
        bbox = draw.textbbox((0, 0), letter, font=font)
        widths.append(bbox[2] - bbox[0])

    total_width = sum(widths) + (tracking * (len(letters) - 1))
    cursor_x = (WIDTH - total_width) // 2

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)

    for letter, width in zip(letters, widths):
        sdraw.text((cursor_x, baseline_y + s(4)), letter, font=font, fill=(255, 255, 255, 38))
        draw.text((cursor_x, baseline_y), letter, font=font, fill=(255, 255, 255, 252))
        cursor_x += width + tracking

    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s(5)))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(wordmark)

    base = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(base)
    bdraw.rounded_rectangle((s(384), s(532), s(816), s(536)), radius=s(2), fill=(255, 255, 255, 22))
    bdraw.rounded_rectangle((s(466), s(556), s(734), s(559)), radius=s(1), fill=YELLOW + (78,))
    base = base.filter(ImageFilter.GaussianBlur(radius=s(1.6)))
    canvas.alpha_composite(base)


def build_card() -> Image.Image:
    canvas = build_background()
    add_composition(canvas)
    add_yellow_accent(canvas)
    return canvas


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    card = build_card()
    export = card.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.Resampling.LANCZOS)
    export = export.filter(ImageFilter.UnsharpMask(radius=1.4, percent=165, threshold=2))
    hi_res = card.filter(ImageFilter.UnsharpMask(radius=2.0, percent=145, threshold=2))
    export.save(BRAND_DIR / "share-card-v4.png")
    export.save(BRAND_DIR / "share-card-v3.png")
    hi_res.save(BRAND_DIR / "share-card-v4@2x.png")


if __name__ == "__main__":
    main()
