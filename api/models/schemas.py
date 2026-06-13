from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model for API request bodies that rejects unexpected fields."""

    model_config = ConfigDict(extra="forbid")


class TentPayload(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    rtsp_url: str | None = Field(default=None, max_length=2048)
    shelly_main_user: str | None = Field(default=None, max_length=200)
    shelly_main_password: str | None = Field(default=None, max_length=512)
    shelly_main_password_clear: bool = False

    @field_validator("name", "source_url", "rtsp_url", "shelly_main_user", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None:
            return None
        return str(value).strip()


class StrainPayload(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    effect: str = Field(min_length=1, max_length=2000)

    @field_validator("name", "effect", mode="before")
    @classmethod
    def strip_strings(cls, value):
        if value is None:
            return ""
        return str(value).strip()


class IrrigationPlanPayload(StrictModel):
    enabled: bool = False
    every_n_days: int = Field(default=1, ge=1, le=365)
    offset_after_light_on_min: int = Field(default=0, ge=0, le=24 * 60)
    last_run_date: date | None = None


class ExhaustVpdPlanPayload(StrictModel):
    enabled: bool = False
    min_vpd_kpa: float = Field(default=0.6, ge=0, le=10)
    hysteresis_kpa: float = Field(default=0.05, ge=0, le=10)


class AuthPayload(StrictModel):
    enabled: bool = False
    username: str | None = None
    password: str | None = None
    twofa_enabled: bool | None = None


class LoginPayload(StrictModel):
    username: str
    password: str
    token: str | None = None
    recovery_code: str | None = None
