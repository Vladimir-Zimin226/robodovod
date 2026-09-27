"""Generate the high-contrast manipulator favicon at every browser icon size."""

from pathlib import Path

from PIL import Image, ImageDraw


PUBLIC = Path(__file__).resolve().parents[1] / "public"
INK = "#142e34"
GREEN = "#09b992"
PAPER = "#f7faf7"
SCALE = 16


def scaled_points(points):
    return [(x * SCALE, y * SCALE) for x, y in points]


def scaled_box(box):
    return tuple(value * SCALE for value in box)


def main():
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img">',
        '<title>РОБОДОВОД — манипулятор</title>',
        f'<rect x="1" y="1" width="62" height="62" rx="12" fill="{PAPER}"/>',
    ]
    canvas = Image.new("RGBA", (64 * SCALE, 64 * SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(scaled_box((1, 1, 63, 63)), radius=12 * SCALE, fill=PAPER)

    for points in (
        [(13, 52), (11, 38), (15, 31), (22, 32), (27, 50)],
        [(17, 28), (36, 11), (43, 17), (25, 35)],
        [(37, 15), (44, 13), (53, 27), (48, 32)],
    ):
        path = " ".join(f"{x},{y}" for x, y in points)
        svg.append(f'<polygon points="{path}" fill="{INK}"/>')
        draw.polygon(scaled_points(points), fill=INK)

    for x, y, radius in ((18, 34, 7), (40, 15, 7), (50, 30, 5)):
        svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{INK}"/>')
        draw.ellipse(scaled_box((x - radius, y - radius, x + radius, y + radius)), fill=INK)
        inner = radius - 2
        svg.append(f'<circle cx="{x}" cy="{y}" r="{inner}" fill="{GREEN}"/>')
        draw.ellipse(scaled_box((x - inner, y - inner, x + inner, y + inner)), fill=GREEN)

    for points in ([(48, 32), (45, 40), (49, 44)], [(52, 32), (56, 37), (53, 43)]):
        path = " ".join(f"{x},{y}" for x, y in points)
        svg.append(
            f'<polyline points="{path}" fill="none" stroke="{INK}" '
            'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        draw.line(scaled_points(points), fill=INK, width=5 * SCALE, joint="curve")
        for x, y in (points[0], points[-1]):
            draw.ellipse(scaled_box((x - 2.5, y - 2.5, x + 2.5, y + 2.5)), fill=INK)

    svg.extend(
        [
            f'<rect x="7" y="50" width="25" height="10" rx="4" fill="{INK}"/>',
            f'<path d="M13 55h13" fill="none" stroke="{GREEN}" '
            'stroke-width="3" stroke-linecap="round"/>',
            "</svg>",
        ]
    )
    draw.rounded_rectangle(scaled_box((7, 50, 32, 60)), radius=4 * SCALE, fill=INK)
    draw.line(scaled_points([(13, 55), (26, 55)]), fill=GREEN, width=3 * SCALE)
    (PUBLIC / "favicon.svg").write_text("".join(svg) + "\n", encoding="utf-8")

    for size in (16, 32, 64, 180, 192, 512):
        name = (
            "apple-touch-icon.png"
            if size == 180
            else f"favicon-{size}.png"
            if size <= 64
            else f"icon-{size}.png"
        )
        canvas.resize((size, size), Image.Resampling.LANCZOS).save(PUBLIC / name)
    canvas.save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])


if __name__ == "__main__":
    main()
