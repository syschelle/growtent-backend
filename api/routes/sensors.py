from fastapi import APIRouter, Depends

from services.sensor_service import SensorService
from core.dependencies import get_sensor_service

router = APIRouter()


@router.get('/tents/{tent_id}/history')
def history_state(tent_id: int, minutes: int = 360, service: SensorService = Depends(get_sensor_service)):
    return service.history(tent_id, minutes)
