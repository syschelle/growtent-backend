import app as legacy


class SensorService:
    def history(self, tent_id: int, minutes: int = 360):
        return legacy.history_state(tent_id, minutes)
