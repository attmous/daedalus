"""Per-frame composition. Glues all the modules together.

Frame layers (bottom → top):

    1. Parchment           — flat cream background plate (parchment.py)
    2. Constellation       — animated node/edge network (constellation.py)
    3. Code overlays       — three editorial code blocks fading in
                              top-right (code_overlays.py)
    4. Margin vignettes    — magnifying glass / doc / curly braces in
                              the right margin (icons.py)
    5. Title block         — caduceus + wordmark emblem + subtitle +
                              tagline + animated workflow flow line
                              (text_block.py + flow.py + icons.py)

Every visual constant comes from ``config`` and every animation curve
from ``timeline`` — this module owns layer order and nothing else.
To retune what an element looks like, edit its module; to retune
*when* it appears, edit ``timeline.py``; to retune colours / anchors,
edit ``config.py``.
"""

from __future__ import annotations

import random

from PIL import Image, ImageDraw

from . import (
    bust as bust_mod,
    code_overlays,
    config,
    constellation,
    icons,
    parchment,
    text_block,
    timeline,
    typography,
)

# Determinism for the constellation seed — the same network every run.
random.seed(7)


class Scene:
    """Pre-baked, frame-invariant pieces. Built once per run."""

    def __init__(self) -> None:
        print("baking parchment …")
        self.parchment = parchment.make_parchment()
        print("preparing bust …")
        # The "bust" image is loaded so its dimensions can anchor the
        # constellation seed point — the image itself is composited
        # into the title block as the wordmark emblem (text_block.py),
        # not pasted as a separate hero plate.
        self.bust = bust_mod.prepare_bust()
        self.bust_pos = bust_mod.placement(self.bust)
        seed_origin = (
            self.bust_pos["x"] + self.bust.width - 60,
            self.bust_pos["y"] + 110,
        )
        self.nodes, self.edges = constellation.build(seed_origin)


def render_frame(scene: Scene, f: int) -> Image.Image:
    """Render frame ``f`` of the banner. ``f`` is in [0, FRAMES)."""
    im = scene.parchment.copy()
    overlay = Image.new("RGBA", (config.W, config.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Loop-tail dim and constellation reveal progress.
    dim = timeline.hold_to_loop(f)
    cp = timeline.constellation_progress(f) * dim

    # Layer 2 — constellation
    constellation.draw(d, scene.nodes, scene.edges, cp, dim)
    im.paste(overlay, (0, 0), overlay)

    # Layer 3 — three code blocks fade in top-right, each on its own
    # RGBA layer so per-block alpha composites cleanly.
    code_layer = Image.new("RGBA", (config.W, config.H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(code_layer)
    code_x = 870
    code_overlays.draw_block(
        cd,
        code_overlays.AGENTS_BLOCK,
        code_x,
        50,
        typography.code(),
        timeline.code_alpha(f, 0),
    )
    code_overlays.draw_block(
        cd,
        code_overlays.GITHUB_BLOCK,
        code_x,
        165,
        typography.code_small(),
        timeline.code_alpha(f, 1),
    )
    code_overlays.draw_block(
        cd,
        code_overlays.TURNLOG_BLOCK,
        code_x,
        250,
        typography.code_small(),
        timeline.code_alpha(f, 2),
    )
    im.paste(code_layer, (0, 0), code_layer)

    # Layer 4 — right-margin editorial vignettes (faded with constellation).
    margin = Image.new("RGBA", (config.W, config.H), (0, 0, 0, 0))
    md = ImageDraw.Draw(margin)
    margin_alpha = int(180 * cp)
    if margin_alpha > 0:
        icons.draw_margin_icons(md, margin_alpha)
    im.paste(margin, (0, 0), margin)

    # Layer 5 — title block on the left. Always opaque except the flow
    # line, which animates stage-by-stage with a pulse. ``text_block``
    # paints onto ``im`` directly so it can paste PNG icons (caduceus,
    # wordmark emblem) and flow.py can blur the pulse glow into the
    # parchment cleanly.
    text_block.draw(im, frame=f)

    return im
