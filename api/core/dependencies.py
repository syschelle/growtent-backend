from typing import Callable

from fastapi import Depends

from services.tent_service import TentService
from services.sensor_service import SensorService
from services.poller_service import PollerService


def get_tent_service() -> TentService:
    return TentService()


def get_sensor_service() -> SensorService:
    return SensorService()


def get_poller_service() -> PollerService:
    return PollerService()
