"""Build small PNG/ICO fallbacks from the same RD geometry as favicon.svg."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "public"
SCALE = 12


def px(value: float) -> int:
    return round(value * SCALE)


def point(*values: float) -> tuple[int, ...]:
    return tuple(px(value) for value in values)


def render(size: int) -> Image.Image:
    canvas = Image.new("RGBA", (64 * SCALE, 64 * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(point(1.5, 1.5, 62.5, 62.5), radius=px(13),
                           fill="#0a1217", outline="#56d8e7", width=px(3))
    white = "#ffffff"
    width = px(6.5)
    draw.line([point(13.5, 46), point(13.5, 18), point(24, 18)], fill=white, width=width, joint="curve")
    draw.arc(point(16, 18, 32, 34), start=270, end=90, fill=white, width=width)
    draw.line([point(24, 34), point(13.5, 34)], fill=white, width=width)
    draw.line([point(24, 34), point(32, 46)], fill=white, width=width)
    draw.line([point(39, 18), point(39, 46), point(42, 46)], fill=white, width=width, joint="curve")
    draw.arc(point(28, 18, 56, 46), start=270, end=90, fill=white, width=width)
    draw.line([point(39, 18), point(42, 18)], fill=white, width=width)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    render(32).save(ROOT / "favicon-32.png")
    render(64).save(ROOT / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    preview = Image.new("RGB", (560, 324), "#ffffff")
    draw = ImageDraw.Draw(preview)
    for column, background in enumerate(("#f5f6f8", "#202833")):
        for row, size in enumerate((16, 32)):
            left, top = column * 280, row * 162
            draw.rectangle((left, top, left + 279, top + 161), fill=background)
            icon = render(size).resize((112, 112), Image.Resampling.NEAREST)
            preview.paste(icon, (left + 84, top + 25), icon)
            label_color = "#111111" if column == 0 else "#ffffff"
            draw.text((left + 10, top + 142), f"{size}px / {'light' if column == 0 else 'dark'} tab", fill=label_color)
    evidence = ROOT.parents[1] / "docs" / "planning" / "assets" / "f7"
    evidence.mkdir(parents=True, exist_ok=True)
    preview.save(evidence / "icon-16-32-light-dark.png")


if __name__ == "__main__":
    main()
