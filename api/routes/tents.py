from fastapi import APIRouter, Depends, Request

from services.tent_service import TentService
from core.dependencies import get_tent_service

router = APIRouter()


@router.get('/tents')
def list_tents(service: TentService = Depends(get_tent_service)):
    return service.list_tents()


@router.post('/tents')
def create_tent(payload: dict, service: TentService = Depends(get_tent_service)):
    return service.create_tent(payload)


@router.put('/tents/{tent_id}')
def update_tent(tent_id: int, payload: dict, service: TentService = Depends(get_tent_service)):
    return service.update_tent(tent_id, payload)


@router.delete('/tents/{tent_id}')
def delete_tent(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.delete_tent(tent_id)


@router.get('/tents/{tent_id}/irrigation-plan')
def get_irrigation_plan(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.get_irrigation_plan(tent_id)


@router.put('/tents/{tent_id}/irrigation-plan')
def update_irrigation_plan(tent_id: int, payload: dict, service: TentService = Depends(get_tent_service)):
    return service.update_irrigation_plan(tent_id, payload)


@router.get('/tents/{tent_id}/exhaust-vpd-plan')
def get_exhaust_vpd_plan(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.get_exhaust_vpd_plan(tent_id)


@router.put('/tents/{tent_id}/exhaust-vpd-plan')
def update_exhaust_vpd_plan(tent_id: int, payload: dict, service: TentService = Depends(get_tent_service)):
    return service.update_exhaust_vpd_plan(tent_id, payload)


@router.get('/tents/{tent_id}/latest')
def latest_state(tent_id: int, request: Request, service: TentService = Depends(get_tent_service)):
    return service.latest(tent_id, request)


@router.get('/tents/{tent_id}/preview')
def preview(
    tent_id: int,
    w: int = 1280,
    h: int = 720,
    q: int = 85,
    service: TentService = Depends(get_tent_service),
):
    return service.preview(tent_id, w=w, h=h, q=q)


@router.get('/tents/{tent_id}/shelly/last-switches')
def shelly_last_switches(tent_id: int, max_rows: int = 5000, service: TentService = Depends(get_tent_service)):
    return service.shelly_last_switches(tent_id, max_rows)


@router.get('/tents/{tent_id}/shelly/main/direct')
def shelly_main_direct_state(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.shelly_main_direct(tent_id)


@router.get('/tents/{tent_id}/shelly/exhaust/direct')
def shelly_exhaust_direct_state(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.shelly_exhaust_direct(tent_id)


@router.get('/tents/{tent_id}/shelly/direct-all')
def shelly_direct_all_state(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.shelly_direct_all(tent_id)


@router.post('/tents/{tent_id}/actions/shelly/{device}/toggle')
def toggle_shelly(tent_id: int, device: str, service: TentService = Depends(get_tent_service)):
    return service.toggle_shelly(tent_id, device)


@router.post('/tents/{tent_id}/actions/shelly/reset-energy')
def reset_shelly_energy(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.reset_shelly_energy(tent_id)


@router.post('/tents/{tent_id}/actions/relay/{relay_idx}/toggle')
def toggle_relay(tent_id: int, relay_idx: int, service: TentService = Depends(get_tent_service)):
    return service.toggle_relay(tent_id, relay_idx)


@router.post('/tents/{tent_id}/actions/startWatering')
def start_watering(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.start_watering(tent_id)


@router.post('/tents/{tent_id}/actions/pump/{pump_idx}/trigger10s')
def trigger_pump(tent_id: int, pump_idx: int, service: TentService = Depends(get_tent_service)):
    return service.trigger_pump(tent_id, pump_idx)


@router.post('/tents/{tent_id}/actions/pingTank')
def ping_tank(tent_id: int, service: TentService = Depends(get_tent_service)):
    return service.ping_tank(tent_id)
