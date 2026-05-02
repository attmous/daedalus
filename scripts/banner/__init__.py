"""Sprints README banner generator.

Generates ``assets/sprints-banner.gif`` — the animated banner shown at
the top of the README. The static counterpart lives at
``assets/sprints-banner.svg`` and is referenced from the README via a
``<picture>`` element so the SVG renders where supported and the GIF
falls back where it isn't.

Public surface::

    from scripts.banner import build
    build()

is equivalent to running::

    python3 scripts/build_banner_gif.py

How to tweak
------------

The package is split so each visual element lives in one module. To
retune the banner, start with ``config.py`` — every colour, font path,
canvas size, and pixel anchor lives there. The other modules only
*render* what ``config`` tells them.

    config.py            single source of truth for paths, palette,
                          canvas size, animation tempo, layout anchors
    timeline.py          per-element animation curves (frame → 0..1)
    typography.py        named font + size pairs
    parchment.py         flat cream background plate
    bust.py              load / chroma-key / size the wordmark emblem
    text_block.py        caduceus + wordmark + subtitle + tagline
    flow.py              animated "Issue → Code → Review → Merge" line
    constellation.py     animated network of nodes + edges
    code_overlays.py     three editorial code blocks (top-right)
    icons.py             caduceus + right-margin vignette icons
    render.py            per-frame composition (layer order)
    encode.py            shared-palette interframe-optimised GIF write

Regenerate::

    python3 scripts/build_banner_gif.py

The script writes to ``assets/sprints-banner.gif`` (~150 KiB).
"""

from __future__ import annotations

from . import config
from .encode import encode
from .render import Scene, render_frame


def build() -> None:
    """Render every frame and encode the loop. Idempotent."""
    print(f"rendering {config.FRAMES} frames @ {config.W}x{config.H} …")
    scene = Scene()
    frames = []
    for i in range(config.FRAMES):
        frames.append(render_frame(scene, i))
        if i % 10 == 0:
            print(f"  frame {i}/{config.FRAMES}")
    encode(frames)


__all__ = ["build", "Scene", "render_frame", "encode", "config"]
