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
        pass

    async def get_state(self) -> dict:
        return self.service.state()

    async def set_binding(self, control: str, binding: dict) -> dict:
        self.service.set_binding(control, binding_from_dict(binding))
        return self.service.state()

    async def set_binding_text(self, control: str, text: str) -> dict:
        try:
            self.service.set_binding(control, parse_binding_text(text))
        except ValueError as e:  # BindingError is a ValueError
            return {"ok": False, "error": str(e), "state": self.service.state()}
        return {"ok": True, "error": None, "state": self.service.state()}

    async def set_dpad_mode(self, mode: str) -> dict:
        self.service.set_dpad_mode(mode)
        return self.service.state()
