"""The settings file: profiles, bindings, game assignments and lighting, with defaults and recovery."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .actuation import DEFAULT_MM, valid_mm
from .bindings import Binding, BindingError, binding_from_dict, binding_to_dict, parse_binding_text
from .devmap import ACTUATION_KEYS, ALL_CONTROLS, FACTORY_OUTPUT

SCHEMA_VERSION = 2
DPAD_MODES = ("4way", "8way")
MAX_PROFILES = 8
DEFAULT_ID = "default"
NAME_MAX = 24
MAX_APP_ID = 2**32 - 1

NO_LEDS = (False, False, False)
# The lit patterns, in the order new profiles get them; Default is always NO_LEDS.
LED_ORDER: Tuple[Tuple[bool, bool, bool], ...] = (
    (True, False, False),
    (False, True, False),
    (False, False, True),
    (True, True, False),
    (True, False, True),
    (False, True, True),
    (True, True, True),
)

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
    leds: Tuple[bool, bool, bool] = NO_LEDS
    actuation: Dict[str, float] = field(default_factory=dict)  # mm, only keys away from DEFAULT_MM


@dataclass
class Game:
    name: str  # for display only
    profile: str


@dataclass
class Config:
    version: int
    profiles: List[Profile]  # Default is always first
    games: Dict[str, Game] = field(default_factory=dict)  # 32-bit app ID as a decimal string
    lighting: Lighting = field(default_factory=Lighting)
    adjustable_actuation: bool = True  # driver mode (key depth) while the plugin has the keypad


class _Corrupt(Exception):
    pass


def factory_bindings() -> Dict[str, Binding]:
    return {control: parse_binding_text(FACTORY_OUTPUT[control]) for control in ALL_CONTROLS}


def default_config() -> Config:
    return Config(version=SCHEMA_VERSION, profiles=[_factory_default()], games={}, lighting=Lighting())


def _factory_default() -> Profile:
    return Profile(id=DEFAULT_ID, name="Default", dpad_mode="4way", bindings=factory_bindings(), leds=NO_LEDS)


def default_profile(c: Config) -> Profile:
    return c.profiles[0]


def find_profile(c: Config, profile_id: str) -> Optional[Profile]:
    for profile in c.profiles:
        if profile.id == profile_id:
            return profile
    return None


def profile_for_app(c: Config, app_id: Optional[int]) -> Profile:
    if app_id is not None:
        game = c.games.get(str(app_id))
        if game is not None:
            profile = find_profile(c, game.profile)
            if profile is not None:
                return profile
    return default_profile(c)


def next_leds(c: Config) -> Tuple[bool, bool, bool]:
    used = {p.leds for p in c.profiles}
    for leds in LED_ORDER:
        if leds not in used:
            return leds
    raise ValueError("no free LED pattern")


def clean_name(c: Config, name: str, exclude_id: Optional[str] = None) -> str:
    name = name.strip()
    if not name or len(name) > NAME_MAX:
        raise ValueError(f"A profile name needs 1 to {NAME_MAX} characters")
    for p in c.profiles:
        if p.id != exclude_id and p.name.casefold() == name.casefold():
            raise ValueError(f"There is already a profile called {p.name!r}")
    return name


def new_profile_id(c: Config) -> str:
    used = {p.id for p in c.profiles}
    n = 2
    while f"p{n}" in used:
        n += 1
    return f"p{n}"


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        return default_config()
    try:
        text = path.read_text()
        data = json.loads(text)
        if isinstance(data, dict) and data.get("version") == 1:
            return _migrate_v1_file(path, text, data)
        return _parse(data)
    except (ValueError, _Corrupt) as e:  # json.JSONDecodeError is a ValueError
        backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        log.warning("settings file unusable (%s); moved to %s, using defaults", e, backup.name)
        os.replace(path, backup)
        return default_config()


def _migrate_v1_file(path: Path, text: str, data: dict) -> Config:
    c = _migrate_v1(data)
    # Keep the v1 bytes next to the new file; a failed write only means the next start retries.
    try:
        _write_atomic(path.with_name(path.name + ".v1-backup"), text)
        save_config(path, c)
        log.info("migrated settings to version %d", SCHEMA_VERSION)
    except OSError as e:
        log.warning("could not write the migrated settings (%s); will retry on the next start", e)
    return c


def _migrate_v1(data: dict) -> Config:
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise _Corrupt("version 1 file without profiles")
    chosen = next((r for r in raw_profiles if isinstance(r, dict) and r.get("id") == data.get("active_profile")),
                  raw_profiles[0])
    if not isinstance(chosen, dict):
        raise _Corrupt("version 1 profile is not an object")
    for raw in raw_profiles:
        if raw is not chosen:
            log.warning("dropping extra version 1 profile %r", raw.get("id") if isinstance(raw, dict) else raw)
    default = _parse_profile(chosen, DEFAULT_ID)
    default.name = "Default"
    return Config(version=SCHEMA_VERSION, profiles=[default], games={}, lighting=_parse_lighting(data.get("lighting")))


def save_config(path: Path, c: Config) -> None:
    _write_atomic(Path(path), json.dumps(_dump(c), indent=2))


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A fresh, exclusively created temp file: the folder belongs to the deck user
    # and the backend runs as root, so never write through a name someone planted.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _dump(c: Config) -> dict:
    return {
        "version": c.version,
        "profiles": [
            {
                "id": p.id,
                "name": p.name,
                "leds": list(p.leds),
                "dpad_mode": p.dpad_mode,
                "bindings": {control: binding_to_dict(b) for control, b in p.bindings.items()},
                "actuation": dict(p.actuation),
            }
            for p in c.profiles
        ],
        "games": {key: {"name": g.name, "profile": g.profile} for key, g in c.games.items()},
        "lighting": {"effect": c.lighting.effect, "color": c.lighting.color, "brightness": c.lighting.brightness},
        "adjustable_actuation": c.adjustable_actuation,
    }


def _parse(data) -> Config:
    if not isinstance(data, dict):
        raise _Corrupt("not a JSON object")
    version = data.get("version")
    if version == 1:
        raise _Corrupt("version 1 reached _parse")  # load_config migrates it first
    if version != SCHEMA_VERSION:
        raise _Corrupt(f"version {version!r}, expected {SCHEMA_VERSION}")
    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, list):
        raise _Corrupt("no profiles")
    profiles = _parse_profiles(raw_profiles)
    return Config(version=SCHEMA_VERSION, profiles=profiles, games=_parse_games(data.get("games"), profiles),
                  lighting=_parse_lighting(data.get("lighting")), adjustable_actuation=_parse_adjustable_actuation(data.get("adjustable_actuation")))


def _parse_profiles(raw_profiles: list) -> List[Profile]:
    # Default first, wherever the file lists it; the rest in file order.
    raw_default = next((r for r in raw_profiles if isinstance(r, dict) and r.get("id") == DEFAULT_ID), None)
    if raw_default is None:
        log.warning("no default profile; recreating it from the factory keys")
        default = _factory_default()
    else:
        default = _parse_profile(raw_default, DEFAULT_ID)
        default.name = _trim_name(raw_default.get("name")) or "Default"
    profiles = [default]
    stored_leds = {DEFAULT_ID: NO_LEDS}
    for raw in raw_profiles:
        if raw is raw_default:
            continue
        if len(profiles) >= MAX_PROFILES:
            log.warning("more than %d profiles; skipping the rest", MAX_PROFILES)
            break
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            log.warning("skipping a profile without an id")
            continue
        pid = raw["id"]
        name = _trim_name(raw.get("name"))
        if name is None:
            log.warning("skipping profile %r: bad name", pid)
        elif any(p.id == pid for p in profiles):
            log.warning("skipping profile %r: duplicate id", pid)
        elif any(p.name.casefold() == name.casefold() for p in profiles):
            log.warning("skipping profile %r: duplicate name %r", pid, name)
        else:
            profile = _parse_profile(raw, pid)
            profile.name = name
            profiles.append(profile)
            stored_leds[pid] = _parse_leds(raw.get("leds"))
    # LED patterns: valid, first-seen stored ones stay; bad or duplicate ones get the next free pattern.
    used = set()
    for profile in profiles[1:]:
        leds = stored_leds[profile.id]
        if leds is not None and leds not in used:
            used.add(leds)
            profile.leds = leds
        else:
            profile.leds = None
    for profile in profiles[1:]:
        if profile.leds is None:
            profile.leds = next(leds for leds in LED_ORDER if leds not in used)
            used.add(profile.leds)
            log.warning("profile %r: bad or duplicate LED pattern; using %s", profile.id, list(profile.leds))
    return profiles


def _trim_name(raw) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    return name if 0 < len(name) <= NAME_MAX else None


def _parse_leds(raw) -> Optional[Tuple[bool, bool, bool]]:
    if isinstance(raw, list) and len(raw) == 3 and all(isinstance(v, bool) for v in raw):
        leds = tuple(raw)
        if leds in LED_ORDER:
            return leds
    return None


def _parse_games(raw, profiles: List[Profile]) -> Dict[str, Game]:
    games: Dict[str, Game] = {}
    if not isinstance(raw, dict):
        return games
    assignable = {p.id for p in profiles[1:]}
    for key, entry in raw.items():
        valid_key = key.isascii() and key.isdigit() and key == str(int(key)) and 0 < int(key) <= MAX_APP_ID
        if not valid_key or not isinstance(entry, dict) or not isinstance(entry.get("profile"), str) \
                or entry["profile"] not in assignable:
            log.warning("dropping game assignment %r", key)
            continue
        name = entry.get("name")
        games[key] = Game(name=name if isinstance(name, str) else key, profile=entry["profile"])
    return games


def _parse_bindings(raw) -> Dict[str, Binding]:
    bindings = factory_bindings()
    if not isinstance(raw, dict):
        return bindings
    for control, value in raw.items():
        if control not in bindings:
            log.warning("dropping binding for unknown control %r", control)
            continue
        try:
            bindings[control] = binding_from_dict(value)
        except BindingError as e:
            log.warning("bad binding for %s (%s); using the factory binding", control, e)
    return bindings


def _parse_profile(raw: dict, pid: str) -> Profile:
    mode = raw.get("dpad_mode")
    return Profile(id=pid, name=pid, dpad_mode=mode if mode in DPAD_MODES else "4way",
                   bindings=_parse_bindings(raw.get("bindings")), actuation=_parse_actuation(raw.get("actuation")))


def _parse_actuation(raw) -> Dict[str, float]:
    actuation: Dict[str, float] = {}
    if not isinstance(raw, dict):
        return actuation
    for control, mm in raw.items():
        if control not in ACTUATION_KEYS or not valid_mm(mm):
            log.warning("dropping actuation %r for %r", mm, control)
        elif round(mm, 1) != DEFAULT_MM:
            actuation[control] = round(mm, 1)
    return actuation


def _parse_adjustable_actuation(raw) -> bool:
    return raw if isinstance(raw, bool) else True


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
