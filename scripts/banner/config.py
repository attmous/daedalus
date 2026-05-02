"""Single source of truth for the README banner generator.

Everything tunable lives in this file — every other module imports
from here and never defines its own colours, sizes, or paths. To
retune the banner you only need to read this one file.

Sections, top to bottom:

    1. Paths        — where things live, where the GIF is written
    2. Fonts        — typeface paths
    3. Canvas       — output dimensions
    4. Palette      — every colour used by the banner
    5. Animation    — total frames + per-frame duration
    6. Layout       — pixel anchors for each element

Each section has a comment header describing what changes when you
tweak it. Stay within one section unless you know why.
"""

from __future__ import annotations

from pathlib import Path

# ════════════════════════════════════════════════════════════════════════
# 1. PATHS
# ════════════════════════════════════════════════════════════════════════
# Where source art is loaded from and where the rendered GIF is written.
# The static counterpart, ``assets/sprints-banner.svg``, lives next to
# the GIF and is referenced from the README alongside it.

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
OUT_PATH = ASSETS / "sprints-banner.gif"

# Ornate "Sprints" wordmark used as the title emblem in the left half.
BUST_SRC = ASSETS / "source" / "sprints-emblem.png"


# ════════════════════════════════════════════════════════════════════════
# 2. FONTS
# ════════════════════════════════════════════════════════════════════════
# Display fonts (Playfair) ship with the repo under ``assets/fonts/`` so
# rendering is reproducible. Mono / sans fall back to system DejaVu —
# replace these paths if you develop on macOS / Windows.
#
# Sizes live with their named roles in ``typography.py``.

FONT_DISPLAY = ASSETS / "fonts" / "PlayfairDisplay.ttf"
FONT_DISPLAY_ITALIC = ASSETS / "fonts" / "PlayfairDisplay-Italic.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ════════════════════════════════════════════════════════════════════════
# 3. CANVAS
# ════════════════════════════════════════════════════════════════════════
# Output dimensions. Keep ``assets/sprints-banner.svg``'s viewBox in
# sync with these values so the GIF and SVG read as the same banner.

W, H = 1200, 400


# ════════════════════════════════════════════════════════════════════════
# 4. PALETTE
# ════════════════════════════════════════════════════════════════════════
# Editorial / parchment palette: cream paper, ink-grey body text, a
# painterly cyan accent for the tagline + workflow pulse, warm gold for
# the caduceus, and a small set of muted hues for the constellation
# nodes. Tuples are RGB; alpha is applied at draw time. Always add new
# colours here — never inline RGB tuples in renderers.

PAPER = (232, 226, 213)         # cream parchment
PAPER_SHADOW = (210, 202, 186)  # subtle shadow ply (currently unused)
INK = (28, 32, 36)              # near-black for body text
INK_SOFT = (76, 84, 92)         # secondary ink for captions / icons
CYAN = (16, 130, 142)           # painterly cyan — tagline, settled flow
CYAN_BRIGHT = (34, 180, 195)    # vivid cyan — flow ignition + pulse
HERMES_GOLD = (165, 132, 60)    # warm gold for the caduceus

# Constellation node + edge colours. Pulled from a muted editorial
# palette so the network reads as ink-on-parchment, not RGB.
NETWORK_COLORS = [
    (110, 70, 60),   # burgundy
    (170, 130, 70),  # ochre
    (60, 110, 110),  # teal-grey
    (120, 130, 90),  # olive
    (90, 80, 110),   # ink-purple
    (160, 100, 80),  # terracotta
]


# ════════════════════════════════════════════════════════════════════════
# 5. ANIMATION
# ════════════════════════════════════════════════════════════════════════
# Frame budget for the whole loop. Higher FRAMES = smoother but bigger
# GIF. DURATION_MS is per-frame display time, so the loop length in ms
# is FRAMES * DURATION_MS.
#
# Per-element timing curves live in ``timeline.py`` — the constants
# below are the only "global" tempo knobs.

FRAMES = 50
DURATION_MS = 80                 # 12.5 fps → 4 s loop


# ════════════════════════════════════════════════════════════════════════
# 6. LAYOUT
# ════════════════════════════════════════════════════════════════════════
# Pixel anchors for the title block on the left and the hero plate on
# the right. Each block has a single (X, Y) origin plus a few size /
# offset knobs — change WORDMARK without disturbing the caduceus or
# the hero plate.

# 6a. Caduceus — tall narrow line drawing on the far-left margin. The
# 1:3 aspect ratio of the Wikimedia source fits naturally as a margin
# emblem. Anchored from the top of the canvas.
CADUCEUS_X = 30
CADUCEUS_Y = 60
CADUCEUS_HEIGHT = 280

# 6b. Title block — the "Sprints" wordmark plus subtitle / tagline /
# flow line. Shifted right of the caduceus.
TITLE_X = 130
TITLE_Y = 70
TITLE_EMBLEM_W = 500             # max width of the wordmark PNG
TITLE_EMBLEM_H = 170             # max height of the wordmark PNG

# Title block vertical offsets, all relative to TITLE_Y. Put new
# typographic lines on their own offset so layout stays inspectable.
OFFSET_SUBTITLE_1 = 170          # "A Hermes-Agent plugin"
OFFSET_SUBTITLE_2 = 218          # cyan tagline
OFFSET_CAPTION_1 = 270           # reserved for future caption line
OFFSET_FLOW = 286                # animated workflow flow

# 6c. Hero plate — the framed engraved image on the right side. Target
# height keeps margin around it so it reads as a plate, not a photo.
BUST_TARGET_H = 155
BUST_TARGET_W = 510
BUST_RIGHT_MARGIN = 40
