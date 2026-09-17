#!/usr/bin/env python3
"""Generate Cognitive Layer logo family, favicon, apple-touch, and og-image.

Geometry from Visual Identity / September 2026:
  240-unit plane width, 100-unit plane depth, 44-unit vertical offset.
  Colour mark: cobalt base; layer blue 85%; signal mint 84%.
  Wordmark: Inter Medium as outlined artwork.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONT_MEDIUM = Path("/usr/share/fonts/truetype/macos/Inter-Medium.ttf")
FONT_REGULAR = Path("/usr/share/fonts/truetype/macos/Inter-Regular.ttf")

INK = "#101C32"
COBALT = "#3155D9"
LAYER_BLUE = "#537DF5"
MINT = "#62D8CC"
WHITE = "#FFFFFF"

INK_RGB = (16, 28, 50)
COBALT_RGB = (49, 85, 217)
LAYER_BLUE_RGB = (83, 125, 245)
MINT_RGB = (98, 216, 204)
WHITE_RGB = (255, 255, 255)

PLANE_W = 240.0
PLANE_D = 100.0
OFFSET = 44.0
# Receding shear so each layer reads as a plane, not a rectangle.
SHEAR = 56.0

BLUE_OPACITY = 0.85
MINT_OPACITY = 0.84

# Mono bands replace overlap with deliberate gaps.
MONO_BAND = 30.0
MONO_GAP = 14.0


def hex_to_rgba(hex_color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, max(0, min(255, round(255 * opacity))))


def plane_points(y: float) -> list[tuple[float, float]]:
    """Parallelogram / chevron plane at vertical origin y (top edge)."""
    return [
        (SHEAR, y),
        (SHEAR + PLANE_W, y),
        (PLANE_W, y + PLANE_D),
        (0.0, y + PLANE_D),
    ]


def color_planes() -> list[tuple[str, float, list[tuple[float, float]]]]:
    # Bottom (base) to top so overlaps composite correctly.
    return [
        (COBALT, 1.0, plane_points(OFFSET * 2)),
        (LAYER_BLUE, BLUE_OPACITY, plane_points(OFFSET)),
        (MINT, MINT_OPACITY, plane_points(0.0)),
    ]


def color_bounds() -> tuple[float, float, float, float]:
    xs, ys = [], []
    for _, _, pts in color_planes():
        xs.extend(p[0] for p in pts)
        ys.extend(p[1] for p in pts)
    return min(xs), min(ys), max(xs), max(ys)


def mono_planes() -> list[list[tuple[float, float]]]:
    """Solid stacked chevrons with negative space between layers."""
    planes = []
    for i in range(3):
        y = i * (MONO_BAND + MONO_GAP)
        planes.append(
            [
                (SHEAR * (MONO_BAND / PLANE_D), y),
                (SHEAR * (MONO_BAND / PLANE_D) + PLANE_W, y),
                (PLANE_W, y + MONO_BAND),
                (0.0, y + MONO_BAND),
            ]
        )
    return planes


def mono_bounds() -> tuple[float, float, float, float]:
    xs, ys = [], []
    for pts in mono_planes():
        xs.extend(p[0] for p in pts)
        ys.extend(p[1] for p in pts)
    return min(xs), min(ys), max(xs), max(ys)


def pts_attr(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.3f},{y:.3f}" for x, y in points)


def load_font() -> TTFont:
    return TTFont(str(FONT_MEDIUM))


def text_path(text: str, font_size: float) -> tuple[str, float, float, float]:
    """Return (svg path d, width, ymin, ymax) with baseline at y=0, x starting at 0."""
    font = load_font()
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm
    scale = font_size / upem
    kern_table = None
    if "kern" in font:
        kern = font["kern"]
        if kern.kernTables:
            kern_table = kern.kernTables[0].kernTable

    x = 0.0
    parts: list[str] = []
    ymin, ymax = 0.0, 0.0
    prev = None
    for ch in text:
        gname = cmap.get(ord(ch), ".notdef")
        if prev is not None and kern_table is not None:
            x += kern_table.get((prev, gname), 0) * scale
        pen = SVGPathPen(glyph_set)
        transform = Transform(scale, 0, 0, -scale, x, 0)
        glyph_set[gname].draw(TransformPen(pen, transform))
        d = pen.getCommands()
        if d:
            parts.append(d)
        glyph = font.getGlyphSet()[gname]
        # Bounds from glyf if available
        glyf = font["glyf"]
        if gname in glyf and glyf[gname].numberOfContours:
            bounds = glyf[gname]
            ymin = min(ymin, -bounds.yMax * scale)
            ymax = max(ymax, -bounds.yMin * scale)
        x += glyph_set[gname].width * scale
        prev = gname
    return " ".join(parts), x, ymin, ymax


def svg_doc(view_w: float, view_h: float, body: str, title: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w:.3f} {view_h:.3f}" '
        f'fill="none" role="img" aria-label="{title}">\n'
        f"  <title>{title}</title>\n"
        f"{body}</svg>\n"
    )


def color_mark_svg(tx: float = 0.0, ty: float = 0.0) -> str:
    parts = []
    for color, opacity, pts in color_planes():
        shifted = [(x + tx, y + ty) for x, y in pts]
        op = "" if opacity == 1 else f' fill-opacity="{opacity:.2f}"'
        parts.append(f'  <polygon fill="{color}"{op} points="{pts_attr(shifted)}"/>\n')
    return "".join(parts)


def mono_mark_svg(color: str, tx: float = 0.0, ty: float = 0.0) -> str:
    parts = []
    for pts in mono_planes():
        shifted = [(x + tx, y + ty) for x, y in pts]
        parts.append(f'  <polygon fill="{color}" points="{pts_attr(shifted)}"/>\n')
    return "".join(parts)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def build_icon_svgs() -> tuple[float, float]:
    minx, miny, maxx, maxy = color_bounds()
    w, h = maxx - minx, maxy - miny
    # Artwork is already origin-tight (miny=0, minx=0).
    write(
        ASSETS / "logo-icon-color.svg",
        svg_doc(w, h, color_mark_svg(), "Cognitive Layer icon"),
    )
    write(
        ASSETS / "logo-icon-color-on-white.svg",
        svg_doc(
            w,
            h,
            f'  <rect width="{w:.3f}" height="{h:.3f}" fill="{WHITE}"/>\n' + color_mark_svg(),
            "Cognitive Layer icon on white",
        ),
    )
    write(
        ASSETS / "logo-icon-color-on-black.svg",
        svg_doc(
            w,
            h,
            f'  <rect width="{w:.3f}" height="{h:.3f}" fill="{INK}"/>\n' + color_mark_svg(),
            "Cognitive Layer icon on black",
        ),
    )

    mminx, mminy, mmaxx, mmaxy = mono_bounds()
    mw, mh = mmaxx - mminx, mmaxy - mminy
    write(
        ASSETS / "logo-icon-mono-ink.svg",
        svg_doc(mw, mh, mono_mark_svg(INK), "Cognitive Layer monochrome icon"),
    )
    write(
        ASSETS / "logo-icon-mono-white.svg",
        svg_doc(mw, mh, mono_mark_svg(WHITE), "Cognitive Layer reverse monochrome icon"),
    )
    return w, h


def build_lockups(icon_w: float, icon_h: float) -> None:
    word = "Cognitive Layer"
    # Understated wordmark relative to the symbol.
    font_size = 54.0
    d, text_w, ymin, ymax = text_path(word, font_size)
    text_h = ymax - ymin
    gap = icon_w * 0.22
    # Vertically centre wordmark to the colour mark.
    text_x = icon_w + gap
    text_baseline = (icon_h / 2.0) - (ymin + ymax) / 2.0

    lockup_w = text_x + text_w
    lockup_h = icon_h

    def lockup(word_fill: str, title: str, bg: str | None = None) -> str:
        body = ""
        if bg:
            body += f'  <rect width="{lockup_w:.3f}" height="{lockup_h:.3f}" fill="{bg}"/>\n'
        body += color_mark_svg()
        body += (
            f'  <path fill="{word_fill}" d="{d}" '
            f'transform="translate({text_x:.3f} {text_baseline:.3f})"/>\n'
        )
        return svg_doc(lockup_w, lockup_h, body, title)

    write(ASSETS / "logo-horizontal.svg", lockup(INK, "Cognitive Layer"))
    write(
        ASSETS / "logo-horizontal-on-white.svg",
        lockup(INK, "Cognitive Layer on white", WHITE),
    )
    write(ASSETS / "logo-horizontal-white.svg", lockup(WHITE, "Cognitive Layer reverse"))
    write(
        ASSETS / "logo-horizontal-on-black.svg",
        lockup(WHITE, "Cognitive Layer on black", INK),
    )

    # Stacked: icon above centred wordmark.
    stack_font = 48.0
    sd, sw, symin, symax = text_path(word, stack_font)
    stack_gap = icon_h * 0.18
    stack_w = max(icon_w, sw)
    stack_h = icon_h + stack_gap + (symax - symin)
    icon_x = (stack_w - icon_w) / 2.0
    word_x = (stack_w - sw) / 2.0
    word_baseline = icon_h + stack_gap - symin
    stacked = color_mark_svg(icon_x, 0.0)
    stacked += (
        f'  <path fill="{INK}" d="{sd}" '
        f'transform="translate({word_x:.3f} {word_baseline:.3f})"/>\n'
    )
    write(ASSETS / "logo-stacked.svg", svg_doc(stack_w, stack_h, stacked, "Cognitive Layer stacked"))

    print(f"horizontal lockup units: {lockup_w:.1f} x {lockup_h:.1f}")
    print(f"stacked lockup units: {stack_w:.1f} x {stack_h:.1f}")


def raster_polygon(
    draw_img: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    scale: float,
    ox: float = 0.0,
    oy: float = 0.0,
) -> None:
    layer = Image.new("RGBA", draw_img.size, (0, 0, 0, 0))
    canvas = ImageDraw.Draw(layer)
    scaled = [(ox + x * scale, oy + y * scale) for x, y in points]
    canvas.polygon(scaled, fill=color)
    draw_img.alpha_composite(layer)


def paint_color_mark(
    img: Image.Image, scale: float, ox: float = 0.0, oy: float = 0.0
) -> None:
    for color, opacity, pts in color_planes():
        raster_polygon(img, pts, hex_to_rgba(color, opacity), scale, ox, oy)


def paint_mono_mark(
    img: Image.Image,
    scale: float,
    color: tuple[int, int, int, int],
    ox: float = 0.0,
    oy: float = 0.0,
) -> None:
    for pts in mono_planes():
        raster_polygon(img, pts, color, scale, ox, oy)


def padded_icon_png(
    path: Path,
    size: int,
    background: tuple[int, int, int, int],
    mono: bool = False,
    mono_color: tuple[int, int, int, int] = (*INK_RGB, 255),
) -> None:
    img = Image.new("RGBA", (size, size), background)
    # Clear space x = 1/4 icon width; square = icon + 2x = 1.5 * icon.
    icon_box = size / 1.5
    if mono:
        minx, miny, maxx, maxy = mono_bounds()
    else:
        minx, miny, maxx, maxy = color_bounds()
    iw, ih = maxx - minx, maxy - miny
    scale = icon_box / max(iw, ih)
    drawn_w, drawn_h = iw * scale, ih * scale
    ox = (size - drawn_w) / 2.0 - minx * scale
    oy = (size - drawn_h) / 2.0 - miny * scale
    if mono:
        paint_mono_mark(img, scale, mono_color, ox, oy)
    else:
        paint_color_mark(img, scale, ox, oy)
    img.save(path, "PNG")
    print(f"wrote {path.relative_to(ROOT)}")


def build_favicons() -> None:
    # SVG favicon: colour icon with tile padding on white.
    minx, miny, maxx, maxy = color_bounds()
    iw, ih = maxx - minx, maxy - miny
    tile = max(iw, ih) * 1.5
    ox = (tile - iw) / 2.0
    oy = (tile - ih) / 2.0
    body = f'  <rect width="{tile:.3f}" height="{tile:.3f}" fill="{WHITE}"/>\n'
    body += color_mark_svg(ox, oy)
    write(ROOT / "favicon.svg", svg_doc(tile, tile, body, "Cognitive Layer"))

    # Multi-size ICO: solid mono at 16–24, colour from 32.
    ico_images: list[Image.Image] = []
    for size, use_mono in ((16, True), (24, True), (32, False), (48, False)):
        img = Image.new("RGBA", (size, size), (*WHITE_RGB, 255))
        if use_mono:
            minx, miny, maxx, maxy = mono_bounds()
        else:
            minx, miny, maxx, maxy = color_bounds()
        box = size / 1.5
        scale = box / max(maxx - minx, maxy - miny)
        dw, dh = (maxx - minx) * scale, (maxy - miny) * scale
        ox = (size - dw) / 2.0 - minx * scale
        oy = (size - dh) / 2.0 - miny * scale
        if use_mono:
            paint_mono_mark(img, scale, (*INK_RGB, 255), ox, oy)
        else:
            paint_color_mark(img, scale, ox, oy)
        ico_images.append(img.convert("RGBA"))

    ico_path = ROOT / "favicon.ico"
    write_ico(ico_path, ico_images)
    print(f"wrote {ico_path.relative_to(ROOT)}")

    padded_icon_png(ROOT / "apple-touch-icon.png", 180, (*WHITE_RGB, 255))
    padded_icon_png(ASSETS / "app-icon-512.png", 512, (*WHITE_RGB, 255))
    padded_icon_png(ASSETS / "logo-icon-color.png", 768, (0, 0, 0, 0))


def write_ico(path: Path, images: list[Image.Image]) -> None:
    """Write a multi-size ICO with PNG-compressed frames."""
    import io
    import struct

    frames = []
    for image in images:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frames.append((image.size[0], image.size[1], buf.getvalue()))

    offset = 6 + 16 * len(frames)
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    payload = b""
    for width, height, raw in frames:
        entries += struct.pack(
            "<BBBBHHII",
            width if width < 256 else 0,
            height if height < 256 else 0,
            0,
            0,
            1,
            32,
            len(raw),
            offset,
        )
        payload += raw
        offset += len(raw)
    path.write_bytes(header + entries + payload)


def build_og_image() -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), WHITE_RGB)
    draw = ImageDraw.Draw(img)

    # Hairline frame — composed, not a wash fill.
    inset = 48
    draw.rectangle([inset, inset, W - inset, H - inset], outline=(*INK_RGB, 255), width=1)

    # Colour mark, generous clear space.
    minx, miny, maxx, maxy = color_bounds()
    mark_h = 86.0
    scale = mark_h / (maxy - miny)
    ox = 88.0
    oy = 88.0
    rgba = img.convert("RGBA")
    paint_color_mark(rgba, scale, ox, oy)
    img = rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    display = ImageFont.truetype(str(FONT_MEDIUM), 56)
    body = ImageFont.truetype(str(FONT_REGULAR), 22)
    label = ImageFont.truetype(str(FONT_MEDIUM), 14)

    draw.text((88, 220), "We solve your biggest", font=display, fill=INK_RGB)
    draw.text((88, 286), "problems with AI.", font=display, fill=INK_RGB)
    draw.text((88, 380), "Intelligence, in layers.", font=body, fill=INK_RGB)
    draw.text((88, 526), "cognitive-layer.com", font=label, fill=COBALT_RGB)

    img.save(ROOT / "og-image.png", "PNG")
    print("wrote og-image.png")

    # Also a 3x horizontal PNG for schema / sharing.
    word = "Cognitive Layer"
    font_size_px = 72
    font = ImageFont.truetype(str(FONT_MEDIUM), font_size_px)
    minx, miny, maxx, maxy = color_bounds()
    icon_h = 96.0
    scale = icon_h / (maxy - miny)
    icon_w = (maxx - minx) * scale
    bbox = font.getbbox(word)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    gap = icon_w * 0.22
    pad = 8
    canvas_w = int(math.ceil(pad * 2 + icon_w + gap + tw))
    canvas_h = int(math.ceil(pad * 2 + max(icon_h, th)))
    lock = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    paint_color_mark(lock, scale, pad, pad + (canvas_h - 2 * pad - icon_h) / 2.0)
    d = ImageDraw.Draw(lock)
    text_y = (canvas_h - th) / 2.0 - bbox[1]
    d.text((pad + icon_w + gap, text_y), word, font=font, fill=(*INK_RGB, 255))
    lock_path = ASSETS / "logo-horizontal.png"
    lock.save(lock_path, "PNG")
    print(f"wrote {lock_path.relative_to(ROOT)}")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon_w, icon_h = build_icon_svgs()
    build_lockups(icon_w, icon_h)
    build_favicons()
    build_og_image()


if __name__ == "__main__":
    main()
