#!/usr/bin/env python3
"""Draw the Default and starter layouts as labelled SVG pictures for the docs.

Usage: render_layouts.py           writes docs/layouts/*.svg
       render_layouts.py --check   writes nothing; exits 1 if a committed picture is out of date

The bindings come from the same data the plugin uses (config.STEAMOS_DEFAULT, starters.STARTERS),
so tests/test_render_layouts.py fails when they drift. What each key is for (the action, a note and
a colour category) is written here, from the tables in docs/starter-profiles.md.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py_modules"))

from tartarus.bindings import Binding, binding_label  # noqa: E402
from tartarus.config import NO_LEDS, profile_from_starter, steamos_bindings  # noqa: E402
from tartarus.starters import STARTERS  # noqa: E402

OUT_DIR = ROOT / "docs" / "layouts"

BG, CARD, EDGE, CHIP, TEXT, MUTED = "#15171b", "#212429", "#2e3238", "#33373f", "#eef0f3", "#8b93a1"
COLOURS = {"green": "#5cbf7a", "orange": "#ef6a4c", "yellow": "#e9bf4f", "blue": "#5b8def", "grey": "#8d939c"}
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

WIDTH, MARGIN = 1160, 28
CARD_W, CARD_H, GAP = 130, 84, 8          # keypad cards
SIDE_W = 122                              # thumb and wheel cards
TOP = 110                                 # first card row
SIDE_X = WIDTH - MARGIN - 3 * SIDE_W - 2 * GAP
WHEEL_Y = TOP + 3 * (CARD_H + GAP) + 42
HEIGHT = WHEEL_Y + CARD_H + MARGIN

# control → (action, note, colour). No action: the card shows the binding itself.
Doc = Mapping[str, Tuple[Optional[str], str, str]]

_DEFAULT_DOC: Doc = {
    "k01": ("Back", "B button", "green"), "k02": (None, "", "blue"), "k03": (None, "", "blue"),
    "k04": (None, "on-screen", "blue"), "k05": (None, "delete text", "green"),
    "k07": ("View", "View button", "yellow"), "k08": ("Options", "Y button", "yellow"),
    "k10": ("Menu", "Menu button", "yellow"),
    "k12": ("Previous tab", "L1", "yellow"), "k13": ("Filter", "X button", "yellow"),
    "k14": ("Next tab", "R1", "yellow"),
    "top_button": ("Select", "A button", "green"),
    "dpad_up": (None, "", "green"), "dpad_right": (None, "", "green"),
    "dpad_down": (None, "", "green"), "dpad_left": (None, "", "green"),
    "wheel_up": ("Volume up", "", "orange"), "wheel_down": ("Volume down", "", "orange"),
    "wheel_click": ("Play / pause", "", "orange"),
}

_FPS_COMMON: Doc = {
    "k01": ("Menu", "deeper press", "grey"), "k06": ("Scoreboard", "or inventory", "grey"),
    "k07": ("Lean left", "or ping", "green"), "k09": ("Lean right", "", "green"),
    "k10": ("Reload", "", "orange"), "k11": ("Sprint", "", "green"), "k16": ("Map", "", "grey"),
    "k17": ("Spare", "prone or ping", "grey"), "k19": ("Crouch", "", "green"),
    "k20": ("Jump", "", "green"), "top_button": ("Slow walk", "or dodge", "green"),
    "wheel_up": ("Holster", "", "yellow"), "wheel_down": ("Melee", "", "orange"),
    "wheel_click": ("Night vision", "", "yellow"),
}

_FPS_WASD_DOC: Doc = {
    **_FPS_COMMON,
    "k02": ("Weapon 1", "", "orange"), "k03": ("Weapon 2", "", "orange"),
    "k04": ("Gadget", "or voice", "yellow"), "k05": ("Interact", "", "yellow"),
    "k08": ("Forward", "", "green"), "k12": ("Left", "", "green"), "k13": ("Back", "", "green"),
    "k14": ("Right", "", "green"), "k15": ("Chat", "", "blue"),
    "k18": ("Grenade", "bipod in Wardogs", "orange"),
    "dpad_up": ("Weapon 3", "or quick use", "orange"), "dpad_right": ("Weapon 4", "or quick use", "orange"),
    "dpad_down": ("Weapon 5", "or quick use", "orange"), "dpad_left": ("Weapon 6", "or quick use", "orange"),
}

_FPS_DPAD_DOC: Doc = {
    **_FPS_COMMON,
    "k02": ("Weapon 1", "", "orange"), "k03": ("Weapon 2", "", "orange"),
    "k04": ("Weapon 3", "", "orange"), "k05": ("Weapon 4", "", "orange"),
    "k08": ("Weapon 5", "", "orange"), "k12": ("Weapon 6", "", "orange"),
    "k13": ("Interact", "", "yellow"), "k14": ("Gadget", "or voice", "yellow"),
    "k15": ("Grenade", "bipod in Wardogs", "orange"), "k18": (None, "free", "grey"),
    "dpad_up": ("Forward", "", "green"), "dpad_right": ("Right", "", "green"),
    "dpad_down": ("Back", "", "green"), "dpad_left": ("Left", "", "green"),
}

_BAR_KEYS = ("k02", "k03", "k04", "k05", "k07", "k08", "k09", "k10", "k12", "k13", "k14", "k15")

_MMO_DOC: Doc = {
    "k01": ("Game menu", "deeper press", "grey"), "k06": ("Next target", "", "orange"),
    **{control: (f"Action {i}", "bar 1", "orange") for i, control in enumerate(_BAR_KEYS, 1)},
    "k11": (None, "modifier", "yellow"), "k16": (None, "modifier", "yellow"),
    "k17": ("Character", "", "blue"), "k18": ("Map", "deeper: B, bags", "blue"),
    "k19": (None, "hold for bar 2", "yellow"), "k20": (None, "modifier", "yellow"),
    "top_button": ("Jump", "", "green"),
    "dpad_up": ("Forward", "", "green"), "dpad_right": ("Right", "", "green"),
    "dpad_down": ("Back", "", "green"), "dpad_left": ("Left", "", "green"),
    "wheel_up": ("Zoom in", "bind in game", "grey"), "wheel_down": ("Zoom out", "bind in game", "grey"),
    "wheel_click": ("Auto-run", "", "green"),
}

_MMO_LAYER_DOC: Doc = {
    **_MMO_DOC,
    **{control: (f"Action {i}", "bar 2", "orange") for i, control in enumerate(_BAR_KEYS, 1)},
}

Legend = Sequence[Tuple[str, str]]
_DEFAULT_LEGEND: Legend = (("green", "Navigate"), ("blue", "Steam"), ("yellow", "Controller buttons"),
                           ("orange", "Media"), ("grey", "Factory key"))
_FPS_LEGEND: Legend = (("green", "Move"), ("orange", "Fight"), ("yellow", "Items"), ("blue", "Talk"),
                       ("grey", "Menus & rare"))
_MMO_LEGEND: Legend = (("green", "Move"), ("orange", "Abilities"), ("yellow", "Modifiers"),
                       ("blue", "Panels"), ("grey", "Menus & rare"))

# slug → (doc, legend, keys drawn with an outline, what the outline means)
_STARTER_DOCS = {
    "fps-wasd": (_FPS_WASD_DOC, _FPS_LEGEND, frozenset({"k08", "k11", "k12", "k13", "k14"}),
                 "fingers rest on the outlined keys"),
    "fps-dpad": (_FPS_DPAD_DOC, _FPS_LEGEND, frozenset(), ""),
    "mmo": (_MMO_DOC, _MMO_LEGEND, frozenset(), ""),
}


def labels_for(bindings: Mapping[str, Binding]) -> Dict[str, str]:
    return {control: binding_label(b) for control, b in bindings.items()}


def _fit(label: str, chars: int) -> str:
    return label if len(label) <= chars else label[:chars - 1] + "…"


def _wrap(text: str, chars: int) -> List[str]:
    """At most two lines, broken between words."""
    words, lines = text.split(), [""]
    for word in words:
        joined = f"{lines[-1]} {word}".strip()
        if len(joined) <= chars or not lines[-1]:
            lines[-1] = joined
        elif len(lines) < 2:
            lines.append(word)
        else:
            lines[-1] = joined
    return [_fit(line, chars) for line in lines]


def _text(x: float, y: float, text: str, size: float, fill: str, anchor: str = "start",
          weight: str = "normal", mono: bool = False, spacing: float = 0) -> str:
    extra = f' font-family="{MONO}"' if mono else ""
    extra += f' letter-spacing="{spacing:g}"' if spacing else ""
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}"{extra}>{escape(text)}</text>')


def _rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none", r: float = 8,
          width: float = 1, dash: str = "") -> str:
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width:g}"{extra}/>')


def _card(x: float, y: float, w: float, caption: str, label: str, entry: Optional[Tuple[Optional[str], str, str]],
          outlined: bool) -> List[str]:
    """A key: a colour bar on top, the key's name, a chip with its binding, then what it does."""
    action, note, colour = entry if entry else (None, "", "grey")
    parts = [_rect(x, y, w, CARD_H, COLOURS[colour]),
             _rect(x, y + 4, w, CARD_H - 4, CARD, EDGE),
             _text(x + 12, y + 24, caption, 11, MUTED, mono=True)]
    if outlined:
        parts.append(_rect(x + 1, y + 1, w - 2, CARD_H - 2, "none", COLOURS["green"], width=2))
    if action and action != label:
        chip_w = len(label) * 6.6 + 12
        parts += [_rect(x + w - 10 - chip_w, y + 11, chip_w, 18, CHIP, r=4),
                  _text(x + w - 10 - chip_w / 2, y + 24, label, 11, TEXT, anchor="middle", weight="bold",
                        mono=True)]
        lines = _wrap(action, int((w - 24) / 8.6))
    else:
        lines = [label]
    for i, line in enumerate(lines):
        parts.append(_text(x + 12, y + 50 + i * 19, line, 16, TEXT, weight="bold"))
    if note:
        parts.append(_text(x + 12, y + 50 + len(lines) * 19, _fit(note, int((w - 24) / 6.4)), 11.5, MUTED))
    return parts


def _width(text: str, size: float) -> float:
    """Roughly how wide a sans-serif string is; the legend has no other way to measure it."""
    def em(ch: str) -> float:
        if ch in "iljI.,:;'| ":
            return 0.28
        if ch in "frt-":
            return 0.36
        if ch in "mwMW":
            return 0.86
        return 0.68 if ch.isupper() or ch == "&" else 0.55
    return sum(em(ch) for ch in text) * size


def _legend(legend: Legend) -> List[str]:
    parts, x = [], WIDTH - MARGIN
    for colour, name in reversed(legend):
        x -= _width(name, 13)
        parts.append(_text(x, 50, name, 13, MUTED))
        x -= 18
        parts.append(_rect(x, 40, 11, 11, COLOURS[colour], r=3))
        x -= 22
    return parts


def render_svg(title: str, labels: Mapping[str, str], highlight: frozenset = frozenset(),
               doc: Optional[Doc] = None, legend: Legend = (), outline_note: str = "") -> str:
    """One picture: keys 01-19 in rows of 5, 5, 5, 4; the top button, D-pad and key 20; the wheel."""
    doc = doc or {}

    def card(x: float, y: float, w: float, caption: str, control: str) -> List[str]:
        return _card(x, y, w, caption, labels.get(control, ""), doc.get(control), control in highlight)

    keypad = "KEYPAD" + (f" · {outline_note.upper()}" if outline_note else "")
    parts = [_rect(0, 0, WIDTH, HEIGHT, BG, r=16),
             _text(MARGIN, 54, title, 28, TEXT, weight="bold"),
             *_legend(legend),
             _text(MARGIN, 96, keypad, 12, MUTED, weight="bold", spacing=1.5),
             _text(SIDE_X, 96, "THUMB", 12, MUTED, weight="bold", spacing=1.5),
             _text(SIDE_X, WHEEL_Y - 14, "WHEEL", 12, MUTED, weight="bold", spacing=1.5)]

    for n in range(1, 20):
        row, col = divmod(n - 1, 5)
        parts += card(MARGIN + col * (CARD_W + GAP), TOP + row * (CARD_H + GAP), CARD_W, f"{n:02d}", f"k{n:02d}")

    def side(col: int, row: int) -> Tuple[float, float]:
        return SIDE_X + col * (SIDE_W + GAP), TOP + row * (CARD_H + GAP)

    for control, caption, col, row in (("top_button", "top", 0, 0), ("dpad_up", "↑ up", 1, 0),
                                       ("dpad_left", "← left", 0, 1), ("dpad_right", "→ right", 2, 1),
                                       ("k20", "20", 0, 2), ("dpad_down", "↓ down", 1, 2)):
        parts += card(*side(col, row), SIDE_W, caption, control)
    cx, cy = side(1, 1)
    parts += [_rect(cx + 14, cy + 4, SIDE_W - 28, CARD_H - 8, "none", EDGE, r=(CARD_H - 8) / 2, width=1.5,
                    dash="4 4"),
              _text(cx + SIDE_W / 2, cy + CARD_H / 2 + 4, "D-pad", 12, MUTED, anchor="middle")]

    for i, (control, caption) in enumerate((("wheel_up", "up"), ("wheel_down", "down"),
                                            ("wheel_click", "click"))):
        parts += card(SIDE_X + i * (SIDE_W + GAP), WHEEL_Y, SIDE_W, caption, control)

    body = "\n  ".join(parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">\n'
            f'  {body}\n</svg>\n')


def all_pictures() -> Dict[str, str]:
    pictures = {"default.svg": render_svg("Default", labels_for(steamos_bindings()), doc=_DEFAULT_DOC,
                                          legend=_DEFAULT_LEGEND)}
    for s in STARTERS:
        doc, legend, outlined, outline_note = _STARTER_DOCS[s.slug]
        profile = profile_from_starter(s, "picture", s.name, NO_LEDS)
        standard = labels_for(profile.bindings)
        pictures[f"{s.slug}.svg"] = render_svg(s.name, standard, highlight=outlined, doc=doc, legend=legend,
                                               outline_note=outline_note)
        if profile.hypershift.bindings:
            layer = labels_for(profile.hypershift.bindings)
            pictures[f"{s.slug}-hypershift.svg"] = render_svg(
                f"{s.name} · Hypershift layer", {**standard, **layer}, highlight=frozenset(layer),
                doc=_MMO_LAYER_DOC, legend=legend, outline_note="outlined keys change while 19 is held")
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
