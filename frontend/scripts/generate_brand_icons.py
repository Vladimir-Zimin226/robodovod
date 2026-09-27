"""Generate the Robodovod pixel robot SVG and raster icons from one shape list."""

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw


PUBLIC = Path(__file__).resolve().parents[1] / "public"
SHAPES = [
    ("round", (2, 2, 62, 62), "#0a1217", 10),
    ("round", (4, 4, 60, 60), "#57d6df", 8),
    ("round", (6, 6, 58, 58), "#0a1217", 7),
    ("rect", (29, 9, 35, 15), "#a3ef58", None),
    ("rect", (30, 15, 34, 20), "#57d6df", None),
    ("rect", (8, 30, 14, 42), "#57d6df", None),
    ("rect", (50, 30, 56, 42), "#57d6df", None),
    ("round", (14, 19, 50, 51), "#17323a", 4),
    ("rect", (20, 27, 29, 36), "#70e7ed", None),
    ("rect", (35, 27, 44, 36), "#70e7ed", None),
    ("rect", (22, 29, 25, 34), "#0a1217", None),
    ("rect", (37, 29, 40, 34), "#0a1217", None),
    ("rect", (23, 42, 29, 46), "#a3ef58", None),
    ("rect", (29, 44, 35, 48), "#a3ef58", None),
    ("rect", (35, 40, 41, 45), "#a3ef58", None),
]


def svg() -> str:
    nodes = []
    for kind, (x1, y1, x2, y2), color, radius in SHAPES:
        tag = "rect"
        attrs = (f'x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" '
                 f'fill="{escape(color)}"')
        if kind == "round":
            attrs += f' rx="{radius}"'
        nodes.append(f"  <{tag} {attrs}/>")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
            'role="img" aria-labelledby="title">\n'
            '  <title id="title">РОБОДОВОД — робот и отметка проверки</title>\n'
            + "\n".join(nodes) + "\n</svg>\n")


def main() -> None:
    (PUBLIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    canvas = Image.new("RGBA", (1024, 1024))
    draw = ImageDraw.Draw(canvas)
    for kind, (x1, y1, x2, y2), color, radius in SHAPES:
        box = (x1 * 16, y1 * 16, x2 * 16 - 1, y2 * 16 - 1)
        if kind == "round":
            draw.rounded_rectangle(box, radius=radius * 16, fill=color)
        else:
            draw.rectangle(box, fill=color)
    for size in (16, 32, 64, 180, 192, 512):
        target = PUBLIC / ("apple-touch-icon.png" if size == 180 else
                           f"favicon-{size}.png" if size in (16, 32, 64) else
                           f"icon-{size}.png")
        canvas.resize((size, size), Image.Resampling.LANCZOS).save(target)
    canvas.save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])


if __name__ == "__main__":
    main()
