import logging

import app as legacy
from fastapi import HTTPException
from db import crud
from models.schemas import GrowProfilePatch, IrrigationPlanPayload, TentPayload
from services.grow_write_service import GrowTentWriteClient, GrowWriteError


LOGGER = logging.getLogger("growtent.write")


class TentService:
    def list_tents(self):
        return crud.list_tents_raw()

    def create_tent(self, payload: TentPayload):
        return crud.create_tent_raw(payload.model_dump(exclude_unset=True))

    def update_tent(self, tent_id: int, payload: TentPayload):
        return crud.update_tent_raw(tent_id, payload.model_dump(exclude_unset=True))

    def delete_tent(self, tent_id: int):
        return crud.delete_tent_raw(tent_id)

    def get_grow_profile(self, tent_id: int):
        cfg = crud.get_tent_write_config_raw(tent_id)
        controller_url = str(cfg.get("backend_controller_url") or "").strip()
        if not controller_url:
            raise HTTPException(status_code=409, detail={"code": "backend_controller_not_configured", "message": "GrowTent controller URL is not configured."})
        # Read endpoints do not require the HMAC secret, but the client validates its constructor.
        # Use a fixed private dummy key only for unsigned GETs; it is never sent anywhere.
        secret = str(cfg.get("_backend_hmac_secret") or "0" * 64)
        try:
            client = GrowTentWriteClient(controller_url, secret)
            state = client.read_profile()
        except GrowWriteError as exc:
            raise HTTPException(status_code=exc.backend_status, detail={"code": exc.code, "message": exc.message})
        return {
            "ok": True,
            "tentId": tent_id,
            "controllerUrl": controller_url,
            "writeEnabled": bool(cfg.get("backend_write_enabled")),
            "state": state,
        }

    def update_grow_profile(self, tent_id: int, payload: GrowProfilePatch, admin_username: str):
        cfg = crud.get_tent_write_config_raw(tent_id)
        patch = payload.model_dump(exclude_unset=True)
        request_id = None
        http_status = None
        result_code = "unknown_error"
        verification_ok = False
        try:
            if not cfg.get("backend_write_enabled"):
                raise GrowWriteError("backend_write_not_enabled", "Backend Write API is not enabled for this tent.", 409)
            controller_url = str(cfg.get("backend_controller_url") or "").strip()
            secret = str(cfg.get("_backend_hmac_secret") or "").strip()
            if not controller_url:
                raise GrowWriteError("backend_controller_not_configured", "GrowTent controller URL is not configured.", 409)
            if not secret:
                raise GrowWriteError("backend_hmac_secret_not_configured", "Backend HMAC secret is not configured for this tent.", 409)

            client = GrowTentWriteClient(controller_url, secret)
            result = client.apply_patch(patch)
            request_id = result.get("requestId")
            http_status = int(result.get("httpStatus") or 202)
            result_code = "ok"
            verification_ok = bool(result.get("verified"))
            return result
        except ValueError as exc:
            result_code = "invalid_grow_profile"
            http_status = 400
            LOGGER.warning(
                "Grow profile write validation failed tent_id=%s fields=%s code=%s",
                tent_id,
                sorted(patch.keys()),
                result_code,
            )
            raise HTTPException(status_code=400, detail={"code": result_code, "message": str(exc)})
        except GrowWriteError as exc:
            request_id = exc.request_id
            http_status = exc.controller_status or exc.backend_status
            result_code = exc.code
            verification_ok = bool(exc.verification_ok)
            LOGGER.warning(
                "Grow profile write failed tent_id=%s fields=%s code=%s controller_status=%s verification_ok=%s",
                tent_id,
                sorted(patch.keys()),
                exc.code,
                exc.controller_status,
                verification_ok,
            )
            raise HTTPException(
                status_code=exc.backend_status,
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "controllerStatus": exc.controller_status,
                    "requestId": exc.request_id,
                },
            )
        finally:
            try:
                crud.insert_grow_write_audit_raw(
                    tent_id=tent_id,
                    tent_name=str(cfg.get("name") or f"Tent {tent_id}"),
                    admin_username=str(admin_username or "admin"),
                    changed_fields=list(patch.keys()),
                    firmware_request_id=request_id,
                    http_status=http_status,
                    result_code=result_code,
                    verification_ok=verification_ok,
                )
            except Exception:
                # The write result must not be changed by an unrelated audit persistence failure.
                # Log identifiers/field names only; never include the secret or signature.
                LOGGER.exception(
                    "Failed to persist grow write audit tent_id=%s fields=%s",
                    tent_id,
                    sorted(patch.keys()),
                )

    def get_irrigation_plan(self, tent_id: int):
        return legacy.get_irrigation_plan(tent_id)

    def update_irrigation_plan(self, tent_id: int, payload: IrrigationPlanPayload):
        return legacy.update_irrigation_plan(tent_id,payload)

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

    def start_watering(self, tent_id: int, payload):
        return legacy.start_watering(tent_id,payload)

    def trigger_pump(self, tent_id: int, pump_idx: int):
        return legacy.trigger_pump_10s(tent_id, pump_idx)

    def ping_tank(self, tent_id: int):
        return legacy.ping_tank(tent_id)
