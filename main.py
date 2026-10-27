from typing import Optional
from pathlib import Path

import decky

from tartarus.bindings import binding_from_dict, parse_binding_text
from tartarus.service import TartarusService


class Plugin:
    service = None  # set by _main; _unload must work even when _main failed part way

    async def _main(self):
        self.service = TartarusService(Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / "settings.json",
                                       decky.emit, decky.logger)
        try:
            await self.service.start()
        except OSError:
            # The panel still loads and shows the keypad as not connected.
            decky.logger.exception("starting the remapping service failed")
            return
        decky.logger.info("Decky Tartarus loaded")

    async def _unload(self):
        if self.service is not None:
            await self.service.stop()
        decky.logger.info("Decky Tartarus unloaded")

    async def _uninstall(self):
        if self.service is not None:
            await self.service.stop()  # Decky calls _unload first; stop is idempotent

    async def get_state(self) -> dict:
        return self.service.state()

    async def set_binding(self, profile_id: str, control: str, binding: dict) -> dict:
        self.service.set_binding(profile_id, control, binding_from_dict(binding))
        return self.service.state()

    async def set_binding_text(self, profile_id: str, control: str, text: str) -> dict:
        try:
            self.service.set_binding(profile_id, control, parse_binding_text(text))
        except ValueError as e:  # BindingError is a ValueError
            return {"ok": False, "error": str(e), "state": self.service.state()}
        return {"ok": True, "error": None, "state": self.service.state()}

    async def set_dpad_mode(self, profile_id: str, mode: str) -> dict:
        self.service.set_dpad_mode(profile_id, mode)
        return self.service.state()

    async def set_running_app(self, app_id: Optional[int], name: Optional[str]) -> dict:
        self.service.set_running_app(app_id, name)
        return self.service.state()

    async def assign_running_game(self, profile_id: str) -> dict:
        self.service.assign_running_game(profile_id)
        return self.service.state()

    async def create_profile(self, name: str, copy_from_id: str) -> dict:
        self.service.create_profile(name, copy_from_id)
        return self.service.state()

    async def rename_profile(self, profile_id: str, name: str) -> dict:
        self.service.rename_profile(profile_id, name)
        return self.service.state()

    async def delete_profile(self, profile_id: str) -> dict:
        self.service.delete_profile(profile_id)
        return self.service.state()

    async def set_lighting(self, effect: str, color: str, brightness: int) -> dict:
        self.service.set_lighting(effect, color, brightness)
        return self.service.state()

    async def set_lighting_enabled(self, enabled: bool) -> dict:
        self.service.set_lighting_enabled(enabled)
        return self.service.state()

    async def set_adjustable_actuation(self, enabled: bool) -> dict:
        self.service.set_adjustable_actuation(enabled)
        return self.service.state()

    async def set_actuation(self, profile_id: str, control: str, mm: float) -> dict:
        self.service.set_actuation(profile_id, control, mm)
        return self.service.state()

    async def set_all_actuation(self, profile_id: str, mm: float) -> dict:
        self.service.set_all_actuation(profile_id, mm)
        return self.service.state()

    async def set_actuation_keys(self, profile_id: str, controls: list, mm: float) -> dict:
        self.service.set_actuation_keys(profile_id, controls, mm)
        return self.service.state()

    async def set_secondary(self, profile_id: str, control: str, mm: Optional[float]) -> dict:
        self.service.set_secondary(profile_id, control, mm)
        return self.service.state()

    async def clear_hypershift_entry(self, profile_id: str, control: str) -> dict:
        self.service.clear_hypershift_entry(profile_id, control)
        return self.service.state()

    async def set_leds(self, profile_id: str, leds: list) -> dict:
        self.service.set_leds(profile_id, leds)
        return self.service.state()

    async def record_start(self) -> None:
        self.service.record_start()

    async def record_cancel(self) -> None:
        self.service.record_cancel()
