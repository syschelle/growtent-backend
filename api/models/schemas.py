from pydantic import BaseModel


class TentPayload(BaseModel):
    name: str
    source_url: str
    rtsp_url: str | None = None
    shelly_main_user: str | None = None
    shelly_main_password: str | None = None


class IrrigationPlanPayload(BaseModel):
    enabled: bool = False
    every_n_days: int = 1
    offset_after_light_on_min: int = 0


class ExhaustVpdPlanPayload(BaseModel):
    enabled: bool = False
    min_vpd_kpa: float = 0.6
    hysteresis_kpa: float = 0.05


class AuthPayload(BaseModel):
    enabled: bool = False
    username: str | None = None
    password: str | None = None
    twofa_enabled: bool | None = None


class LoginPayload(BaseModel):
    username: str
    password: str
    token: str | None = None
    recovery_code: str | None = None
