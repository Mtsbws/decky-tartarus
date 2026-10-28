#!/usr/bin/env python3
"""Draw the Default and starter layouts as labelled SVG pictures for the docs.

Usage: render_layouts.py           writes docs/layouts/*.svg
       render_layouts.py --check   writes nothing; exits 1 if a committed picture is out of date

The pictures come from the same data the plugin uses (config.STEAMOS_DEFAULT, starters.STARTERS),
so tests/test_render_layouts.py fails when they drift.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Mapping
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py_modules"))

from tartarus.bindings import Binding, binding_label  # noqa: E402
from tartarus.config import NO_LEDS, profile_from_starter, steamos_bindings  # noqa: E402
from tartarus.starters import STARTERS  # noqa: E402

OUT_DIR = ROOT / "docs" / "layouts"

WIDTH, HEIGHT = 800, 456
BG, CARD, KEY, KEY_EDGE, TEXT, MUTED, ACCENT = (
    "#e6e8ec", "#1d2027", "#2b3039", "#3a404b", "#eef0f3", "#8b93a1", "#44d62c")

KEY_W, KEY_H, GAP = 96, 56, 8
GRID_X, GRID_Y = 40, 72
SIDE_X, SIDE_W = 584, 176
DPAD_W, DPAD_H = 56, 40


def labels_for(bindings: Mapping[str, Binding]) -> Dict[str, str]:
    return {control: binding_label(b) for control, b in bindings.items()}


def _fit(label: str, chars: int) -> str:
    return label if len(label) <= chars else label[:chars - 1] + "…"


def _text(x: float, y: float, text: str, size: int, fill: str, anchor: str = "middle", weight: str = "normal") -> str:
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{escape(text)}</text>')


def _rect(x: float, y: float, w: float, h: float, fill: str, stroke: str, r: int = 8) -> str:
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'


def _key(x: float, y: float, w: float, h: float, caption: str, label: str, chars: int, edge: str) -> List[str]:
    return [_rect(x, y, w, h, KEY, edge),
            _text(x + 8, y + 15, caption, 10, MUTED, anchor="start"),
            _text(x + w / 2, y + h / 2 + 10, _fit(label, chars), 13, TEXT, weight="bold")]


def render_svg(title: str, labels: Mapping[str, str], highlight: frozenset = frozenset()) -> str:
    """One picture: keys 01-19 in rows of 5, 5, 5, 4, then the wheel, top button, D-pad and key 20."""
    def edge(control: str) -> str:
        return ACCENT if control in highlight else KEY_EDGE

    def label(control: str) -> str:
        return labels.get(control, "")

    parts = [_rect(0, 0, WIDTH, HEIGHT, BG, BG, r=0),
             _rect(16, 16, WIDTH - 32, HEIGHT - 32, CARD, CARD, r=16),
             _text(40, 52, title, 18, TEXT, anchor="start", weight="bold")]

    for n in range(1, 20):
        row, col = divmod(n - 1, 5)
        control = f"k{n:02d}"
        parts += _key(GRID_X + col * (KEY_W + GAP), GRID_Y + row * (KEY_H + GAP), KEY_W, KEY_H,
                      f"{n:02d}", label(control), 12, edge(control))

    # The wheel: one box, a row each for up, click and down.
    y = GRID_Y
    parts.append(_rect(SIDE_X, y, SIDE_W, 88, KEY, KEY_EDGE))
    for i, (control, caption) in enumerate((("wheel_up", "wheel ▲"), ("wheel_click", "click"),
                                            ("wheel_down", "wheel ▼"))):
        row_y = y + 22 + i * 26
        parts.append(_text(SIDE_X + 10, row_y, caption, 10, MUTED, anchor="start"))
        parts.append(_text(SIDE_X + SIDE_W - 10, row_y, _fit(label(control), 14), 13, TEXT, anchor="end",
                           weight="bold"))

    parts += _key(SIDE_X, GRID_Y + 100, SIDE_W, 44, "top", label("top_button"), 18, edge("top_button"))

    # The D-pad as a cross.
    cx, top = SIDE_X + SIDE_W / 2, GRID_Y + 156
    cells = {"dpad_up": (cx - DPAD_W / 2, top), "dpad_left": (cx - DPAD_W * 1.5, top + DPAD_H),
             "dpad_right": (cx + DPAD_W / 2, top + DPAD_H), "dpad_down": (cx - DPAD_W / 2, top + DPAD_H * 2)}
    for control, (x, cell_y) in cells.items():
        parts.append(_rect(x, cell_y, DPAD_W, DPAD_H, KEY, edge(control), r=6))
        parts.append(_text(x + DPAD_W / 2, cell_y + DPAD_H / 2 + 5, _fit(label(control), 7), 13, TEXT,
                           weight="bold"))
    parts.append(_rect(cx - DPAD_W / 2, top + DPAD_H, DPAD_W, DPAD_H, KEY_EDGE, KEY_EDGE, r=6))

    parts += _key(SIDE_X, GRID_Y + 296, SIDE_W, KEY_H, "20", label("k20"), 18, edge("k20"))

    body = "\n  ".join(parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica, Arial, sans-serif">\n'
            f'  {body}\n</svg>\n')


def all_pictures() -> Dict[str, str]:
    pictures = {"default.svg": render_svg("Default", labels_for(steamos_bindings()))}
    for s in STARTERS:
        profile = profile_from_starter(s, "picture", s.name, NO_LEDS)
        standard = labels_for(profile.bindings)
        slug = s.id.split(":", 1)[1]
        pictures[f"{slug}.svg"] = render_svg(s.name, standard)
        if profile.hypershift.bindings:
            layer = labels_for(profile.hypershift.bindings)
            pictures[f"{slug}-hypershift.svg"] = render_svg(
                f"{s.name} – Hypershift layer (hold the Hypershift key)", {**standard, **layer},
                highlight=frozenset(layer))
    return pictures


def main(argv: List[str]) -> int:
    pictures = all_pictures()
    if argv == ["--check"]:
        stale = [name for name, svg in pictures.items()
                 if not (OUT_DIR / name).exists() or (OUT_DIR / name).read_text(encoding="utf-8") != svg]
        for name in stale:
            print(f"out of date: docs/layouts/{name}")
        return 1 if stale else 0
    if argv:
        print(__doc__)
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg in pictures.items():
        (OUT_DIR / name).write_text(svg, encoding="utf-8")
        print(f"wrote docs/layouts/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
