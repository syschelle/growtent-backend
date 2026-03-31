import app as legacy


class PollerService:
    def startup(self):
        # Keep original startup behavior unchanged.
        return legacy.startup_event()
