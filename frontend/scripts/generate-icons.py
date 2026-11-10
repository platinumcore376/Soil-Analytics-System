# -*- coding: utf-8 -*-
"""Generate the app icon set — run with `python scripts/generate-icons.py` (needs Pillow).

Regenerate after changing the palette or the mark. Outputs into `public/icons/` plus
`public/favicon.ico`. Committed so the icons are reproducible rather than opaque binaries.

DESIGN CONSTRAINTS, in priority order
1. Legible at 16x16. A browser tab is the smallest and most common appearance. The old icon
   put a 2px-wide white stalk over a flat brown rectangle; at 16px the stalk disappeared and
   what remained was an unidentifiable brown block.
2. Recognisable as soil + growth. Two shapes only: layered ground, and a sprout above it.
3. Matches the app's palette exactly — theme_color #2f9e44, surface #f7f7f5.
4. Works as a maskable icon, where Android may crop to a circle. Content stays inside the
   safe zone (central 80% diameter).

Rendered at 4x then downsampled with LANCZOS, which is what gives clean edges at small sizes.
"""
import pathlib

from PIL import Image, ImageDraw

# Relative to this file, so the script runs from anywhere.
OUT = pathlib.Path(__file__).resolve().parent.parent / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

GREEN = (47, 158, 68)        # #2f9e44 — theme colour
GREEN_DK = (32, 122, 51)
LEAF = (126, 217, 87)        # bright enough to read against the green field
SOIL_TOP = (109, 76, 51)     # topsoil, darkest
SOIL_MID = (140, 98, 62)
SOIL_LOW = (176, 132, 84)    # subsoil, lightest — the stratification reads as "soil layers"
WHITE = (255, 255, 255)

SS = 4  # supersample factor


def rounded_rect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def draw_icon(size: int, *, maskable: bool = False, circle_bg: bool = False) -> Image.Image:
    """One icon. `maskable` shrinks content into the safe zone; `circle_bg` for favicons.

    Below 24px the icon switches to a SIMPLIFIED form: a single soil band instead of three,
    and a larger sprout. Three 1px bands average into one flat brown smear at that size, and
    the detail actively costs legibility rather than adding to it. This is the standard
    favicon approach — the small sizes are a different drawing, not a scaled-down big one.
    """
    tiny = size < 24
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- background
    if circle_bg:
        d.ellipse([0, 0, S - 1, S - 1], fill=GREEN)
    else:
        # Squircle-ish: Android/iOS both mask, so a generous radius avoids visible corners.
        rounded_rect(d, [0, 0, S - 1, S - 1], int(S * 0.22), GREEN)

    # Content scale. A maskable icon may be cropped to a circle, so keep everything well in.
    inset = 0.30 if maskable else (0.10 if tiny else 0.17)
    x0, x1 = S * inset, S * (1 - inset)
    w = x1 - x0

    # ---- soil block: three bands, thick enough that each survives downsampling
    soil_top_y = S * (0.55 if maskable else (0.58 if tiny else 0.52))
    soil_bot_y = S * (1 - inset - 0.02)
    band = (soil_bot_y - soil_top_y) / 3.0
    radius = int(w * 0.10)

    # Draw as one rounded block, then overlay the lower two bands so only the outer corners
    # are rounded — square internal seams read as strata rather than as stacked pills.
    if tiny:
        # One solid band. Mid-tone brown holds the most contrast against both the green field
        # and the white stem.
        rounded_rect(d, [x0, soil_top_y, x1, soil_bot_y], radius, SOIL_MID)
    else:
        rounded_rect(d, [x0, soil_top_y, x1, soil_bot_y], radius, SOIL_TOP)
        d.rectangle([x0, soil_top_y + band, x1, soil_top_y + 2 * band], fill=SOIL_MID)
        rounded_rect(d, [x0, soil_top_y + 2 * band, x1, soil_bot_y], radius, SOIL_LOW)
        d.rectangle(
            [x0, soil_top_y + 2 * band, x1, soil_top_y + 2 * band + radius], fill=SOIL_LOW
        )

    # ---- sprout: stem + two leaves.
    # The stem is deliberately thick (7% of width). The old icon's hairline stem was the
    # single reason the whole mark failed at 16px.
    cx = (x0 + x1) / 2
    stem_w = max(2 * SS, w * (0.13 if tiny else 0.075))
    stem_top = S * (0.20 if not maskable else 0.26)
    d.rounded_rectangle(
        [cx - stem_w / 2, stem_top, cx + stem_w / 2, soil_top_y + band * 0.5],
        radius=stem_w / 2,
        fill=WHITE,
    )

    # Two teardrop leaves, angled up. Ellipses keep the silhouette solid at small sizes.
    leaf_w, leaf_h = (w * 0.52, w * 0.34) if tiny else (w * 0.42, w * 0.26)
    ly = stem_top + leaf_h * 0.15
    d.ellipse([cx - leaf_w, ly - leaf_h / 2, cx + stem_w * 0.2, ly + leaf_h / 2], fill=WHITE)
    # At tiny sizes LEAF green sits too close to the background green to separate.
    d.ellipse(
        [cx - stem_w * 0.2, ly - leaf_h / 2, cx + leaf_w, ly + leaf_h / 2],
        fill=WHITE if tiny else LEAF,
    )

    return img.resize((size, size), Image.LANCZOS)


def flatten(img: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    out = Image.new("RGB", img.size, bg)
    out.paste(img, mask=img.split()[3])
    return out


# ---- PWA / Apple icons
draw_icon(192).save(OUT / "icon-192.png")
draw_icon(512).save(OUT / "icon-512.png")
draw_icon(512, maskable=True).save(OUT / "icon-maskable-512.png")
# Apple touch icons must not be transparent — iOS composites them onto black otherwise.
flatten(draw_icon(180)).save(OUT / "apple-touch-icon.png")

# ---- favicons. A circle background reads better than a squircle at 16-32px.
for s in (16, 32, 48):
    draw_icon(s, circle_bg=True).save(OUT / f"favicon-{s}.png")

# Multi-resolution .ico, written by hand.
#
# Two reasons not to use Pillow's ICO writer here:
#   * given one large image it downscales for every frame, reintroducing the 16px mush the
#     `tiny` branch exists to prevent;
#   * `append_images` was silently dropped, leaving a single-frame file.
# The container format is trivial — a 6-byte header, a 16-byte directory entry per frame, then
# the PNG payloads — so writing it directly is both shorter and verifiable.
def write_ico(path: pathlib.Path, images: list[Image.Image]) -> None:
    import io
    import struct

    blobs = []
    for im in images:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        blobs.append(buf.getvalue())

    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, type=icon, count
    offset = 6 + 16 * len(images)
    entries, payload = b"", b""
    for im, blob in zip(images, blobs):
        # 0 in the width/height byte means 256.
        w = 0 if im.width >= 256 else im.width
        h = 0 if im.height >= 256 else im.height
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), offset)
        payload += blob
        offset += len(blob)
    path.write_bytes(header + entries + payload)


write_ico(
    OUT.parent / "favicon.ico",
    [draw_icon(s, circle_bg=True) for s in (16, 24, 32, 48, 64, 128, 256)],
)

for f in sorted(OUT.glob("*.png")) + [OUT.parent / "favicon.ico"]:
    print("%-28s %6d bytes" % (f.name, f.stat().st_size))
