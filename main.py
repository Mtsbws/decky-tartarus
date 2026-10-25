import decky


class Plugin:
    # Filled in by Task 8: build and start the TartarusService.
    async def _main(self):
        decky.logger.info("Decky Tartarus loaded")

    # Filled in by Task 8: stop the service (ungrab, destroy virtual devices).
    async def _unload(self):
        decky.logger.info("Decky Tartarus unloaded")

    async def _uninstall(self):
        pass
