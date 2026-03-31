import app as legacy
from db import crud


class TentService:
    def list_tents(self):
        return crud.list_tents_raw()

    def create_tent(self, payload: dict):
        return crud.create_tent_raw(payload)

    def update_tent(self, tent_id: int, payload: dict):
        return crud.update_tent_raw(tent_id, payload)

    def delete_tent(self, tent_id: int):
        return crud.delete_tent_raw(tent_id)

    def get_irrigation_plan(self, tent_id: int):
        return crud.get_irrigation_plan_raw(tent_id)

    def update_irrigation_plan(self, tent_id: int, payload: dict):
        return crud.update_irrigation_plan_raw(tent_id, payload)

    def get_exhaust_vpd_plan(self, tent_id: int):
        return crud.get_exhaust_vpd_plan_raw(tent_id)

    def update_exhaust_vpd_plan(self, tent_id: int, payload: dict):
        return crud.update_exhaust_vpd_plan_raw(tent_id, payload)

    def latest(self, tent_id: int, request):
        return legacy.latest_state(tent_id, request)

    def preview(self, tent_id: int, w: int = 1280, h: int = 720, q: int = 85):
        return legacy.tent_preview(tent_id, w=w, h=h, q=q)

    def shelly_last_switches(self, tent_id: int, max_rows: int):
        return legacy.shelly_last_switches(tent_id, max_rows)

    def history(self, tent_id: int, minutes: int):
        return legacy.history_state(tent_id, minutes)

    def shelly_main_direct(self, tent_id: int):
        return legacy.shelly_main_direct_state(tent_id)

    def shelly_exhaust_direct(self, tent_id: int):
        return legacy.shelly_exhaust_direct_state(tent_id)

    def shelly_direct_all(self, tent_id: int):
        return legacy.shelly_direct_all_state(tent_id)

    def toggle_shelly(self, tent_id: int, device: str):
        return legacy.toggle_shelly_device(tent_id, device)

    def reset_shelly_energy(self, tent_id: int):
        return legacy.reset_shelly_energy(tent_id)

    def toggle_relay(self, tent_id: int, relay_idx: int):
        return legacy.toggle_relay(tent_id, relay_idx)

    def start_watering(self, tent_id: int):
        return legacy.start_watering(tent_id)

    def trigger_pump(self, tent_id: int, pump_idx: int):
        return legacy.trigger_pump_10s(tent_id, pump_idx)

    def ping_tank(self, tent_id: int):
        return legacy.ping_tank(tent_id)
