"""The settings file: profiles, bindings and lighting, with defaults and recovery."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .bindings import Binding, BindingError, binding_from_dict, binding_to_dict, parse_binding_text
from .devmap import ALL_CONTROLS, FACTORY_OUTPUT

SCHEMA_VERSION = 1
DPAD_MODES = ("4way", "8way")

log = logging.getLogger("tartarus")


@dataclass
class Lighting:
    effect: str = "spectrum"
    color: str = "#00ff00"
    brightness: int = 100


@dataclass
class Profile:
    id: str
    name: str
    dpad_mode: str  # "4way" | "8way"
    bindings: Dict[str, Binding]


@dataclass
class Config:
    version: int
    active_profile: str
    profiles: List[Profile]
    lighting: Lighting = field(default_factory=Lighting)


class _Corrupt(Exception):
    pass


def factory_bindings() -> Dict[str, Binding]:
    return {control: parse_binding_text(FACTORY_OUTPUT[control]) for control in ALL_CONTROLS}


def default_config() -> Config:
    profile = Profile(id="default", name="Default", dpad_mode="4way", bindings=factory_bindings())
    return Config(version=SCHEMA_VERSION, active_profile="default", profiles=[profile], lighting=Lighting())


def active_profile(c: Config) -> Profile:
    for profile in c.profiles:
        if profile.id == c.active_profile:
            return profile
    return c.profiles[0]


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        return default_config()
    try:
        return _parse(json.loads(path.read_text()))
    except (ValueError, _Corrupt) as e:  # json.JSONDecodeError is a ValueError
        backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        log.warning("settings file unusable (%s); moved to %s, using defaults", e, backup.name)
        os.replace(path, backup)
        return default_config()


def save_config(path: Path, c: Config) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A fresh, exclusively created temp file: the folder belongs to the deck user
    # and the backend runs as root, so never write through a name someone planted.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w") as f:
            json.dump(_dump(c), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _dump(c: Config) -> dict:
    return {
        "version": c.version,
        "active_profile": c.active_profile,
        "profiles": [
            {
                "id": p.id,
                "name": p.name,
                "dpad_mode": p.dpad_mode,
                "bindings": {control: binding_to_dict(b) for control, b in p.bindings.items()},
            }
            for p in c.profiles
        ],
        "lighting": {"effect": c.lighting.effect, "color": c.lighting.color, "brightness": c.lighting.brightness},
    }


def _parse(data) -> Config:
    if not isinstance(data, dict):
        raise _Corrupt("not a JSON object")
    if data.get("version") != SCHEMA_VERSION:
        raise _Corrupt(f"version {data.get('version')!r}, expected {SCHEMA_VERSION}")
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise _Corrupt("no profiles")
    profiles = [_parse_profile(p) for p in raw_profiles]
    active = data.get("active_profile")
    if active not in {p.id for p in profiles}:
        active = profiles[0].id
    return Config(version=SCHEMA_VERSION, active_profile=active, profiles=profiles,
                  lighting=_parse_lighting(data.get("lighting")))


def _parse_profile(raw) -> Profile:
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
        raise _Corrupt("profile without an id")
    stored = raw.get("bindings")
    if not isinstance(stored, dict):
        stored = {}
    bindings = factory_bindings()
    for control, value in stored.items():
        if control not in bindings:
            log.warning("dropping binding for unknown control %r", control)
            continue
        try:
            bindings[control] = binding_from_dict(value)
        except BindingError as e:
            log.warning("bad binding for %s (%s); using the factory binding", control, e)
    mode = raw.get("dpad_mode")
    return Profile(
        id=raw["id"],
        name=raw.get("name") if isinstance(raw.get("name"), str) else raw["id"],
        dpad_mode=mode if mode in DPAD_MODES else "4way",
        bindings=bindings,
    )


def _parse_lighting(raw) -> Lighting:
    lighting = Lighting()
    if not isinstance(raw, dict):
        return lighting
    if isinstance(raw.get("effect"), str):
        lighting.effect = raw["effect"]
    if isinstance(raw.get("color"), str):
        lighting.color = raw["color"]
    brightness = raw.get("brightness")
    if isinstance(brightness, int) and not isinstance(brightness, bool) and 0 <= brightness <= 100:
        lighting.brightness = brightness
    return lighting
