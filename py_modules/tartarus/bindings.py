"""What a control does: the Binding type, its JSON form, text grammar and labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .codes import canonical, category

BINDING_TYPES = ("key", "shortcut", "combo", "modifier", "macro", "mouse", "media", "disable", "steam", "hypershift")
STEAM_ACTIONS = ("menu", "qam")
SINGLE_TYPES = ("key", "modifier", "mouse", "media")

_STEAM_LABELS = {"menu": "Steam menu", "qam": "Quick Access"}


class BindingError(ValueError):
    pass


@dataclass(frozen=True)
class Binding:
    type: str
    keys: Tuple[str, ...] = ()
    steps: Tuple[Tuple[str, ...], ...] = ()
    action: str = ""


def _names(names: Iterable[str]) -> Tuple[str, ...]:
    out = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise BindingError("empty key name")
        try:
            out.append(canonical(name))
        except KeyError:
            raise BindingError(f"unknown key: {name.strip()}") from None
    if not out:
        raise BindingError("no keys given")
    if len(set(out)) != len(out):
        raise BindingError("a key appears twice")
    return tuple(out)


def _split_plus(text: str) -> Tuple[str, ...]:
    # "Vol+" contains the separator, so an empty token right after "Vol" joins it.
    parts = text.split("+")
    names = []
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.lower() == "vol" and i + 1 < len(parts) and parts[i + 1] == "":
            names.append("Vol+")
            i += 2
            continue
        if part == "":
            raise BindingError(f"missing key in '{text}'")
        names.append(part)
        i += 1
    return _names(names)


def _single(name: str) -> Binding:
    return Binding(category(name), (name,))


def parse_binding_text(text: str) -> Binding:
    text = "".join(text.split())
    if not text:
        raise BindingError("empty binding")
    lower = text.lower()
    if lower == "disable":
        return Binding("disable")
    if lower == "hypershift":
        return Binding("hypershift")
    if lower.startswith("steam:"):
        action = lower[len("steam:"):]
        if action not in STEAM_ACTIONS:
            raise BindingError(f"unknown Steam action: {action}")
        return Binding("steam", action=action)
    if lower.startswith("hold:"):
        return Binding("combo", _split_plus(text[len("hold:"):]))
    if "," in text:
        steps = tuple(_split_plus(step) for step in text.split(","))
        if len(steps) < 2:
            raise BindingError("a macro needs at least two steps")
        return Binding("macro", steps=steps)
    keys = _split_plus(text)
    if len(keys) == 1:
        return _single(keys[0])
    return Binding("shortcut", keys)


def binding_to_dict(b: Binding) -> dict:
    if b.type == "macro":
        return {"type": "macro", "steps": [list(step) for step in b.steps]}
    if b.type == "steam":
        return {"type": "steam", "action": b.action}
    if b.type == "disable":
        return {"type": "disable"}
    if b.type == "hypershift":
        return {"type": "hypershift"}
    return {"type": b.type, "keys": list(b.keys)}


def binding_from_dict(d: dict) -> Binding:
    if not isinstance(d, dict):
        raise BindingError("binding must be an object")
    kind = d.get("type")
    if kind not in BINDING_TYPES:
        raise BindingError(f"unknown binding type: {kind!r}")
    if kind == "disable":
        return Binding("disable")
    if kind == "hypershift":
        return Binding("hypershift")
    if kind == "steam":
        action = d.get("action")
        if action not in STEAM_ACTIONS:
            raise BindingError(f"unknown Steam action: {action!r}")
        return Binding("steam", action=action)
    if kind == "macro":
        steps = d.get("steps")
        if not isinstance(steps, list) or not steps:
            raise BindingError("a macro needs steps")
        return Binding("macro", steps=tuple(_names(_as_list(step)) for step in steps))
    keys = _names(_as_list(d.get("keys")))
    if kind in SINGLE_TYPES:
        if len(keys) != 1 or category(keys[0]) != kind:
            raise BindingError(f"{kind} binding needs exactly one {kind} name")
    elif kind == "shortcut" and len(keys) < 2:
        raise BindingError("a shortcut needs at least two keys")
    return Binding(kind, keys)


def _as_list(value) -> list:
    if not isinstance(value, list):
        raise BindingError("keys must be a list")
    return value


def binding_label(b: Binding) -> str:
    if b.type in SINGLE_TYPES:
        return b.keys[0]
    if b.type == "shortcut":
        return "+".join(b.keys)
    if b.type == "combo":
        return "+".join(b.keys) + " (hold)"
    if b.type == "macro":
        return ", ".join("+".join(step) for step in b.steps)
    if b.type == "steam":
        return _STEAM_LABELS[b.action]
    if b.type == "hypershift":
        return "Hypershift"
    return "—"
