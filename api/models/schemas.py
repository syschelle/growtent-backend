from datetime import date
from typing import Literal

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
    pot_strains: dict[str, str] = Field(default_factory=dict)

    @field_validator("name", "source_url", "rtsp_url", "shelly_main_user", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None:
            return None
        return str(value).strip()

    @field_validator("pot_strains", mode="before")
    @classmethod
    def normalize_pot_strains(cls, value):
        if not isinstance(value, dict):
            return {}
        return {
            f"pot{idx}": str(value.get(f"pot{idx}") or "").strip()
            for idx in range(1, 4)
        }


class StrainPayload(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    genetics: Literal["Sativa", "Indica", "Sativa-hybrid", "Indica-hybrid", "50/50"]
    thc: str = Field(default="", max_length=100)
    cbd: str = Field(default="", max_length=100)
    effects: str = Field(default="", max_length=2000)
    aroma: str = Field(default="", max_length=2000)

    @field_validator(
        "name",
        "thc",
        "cbd",
        "effects",
        "aroma",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value):
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("genetics", mode="before")
    @classmethod
    def normalize_genetics(cls, value):
        normalized = str(value or "").strip().casefold()
        if normalized == "sativa":
            return "Sativa"
        if normalized == "indica":
            return "Indica"
        compact = normalized.replace(" ", "").replace("_", "-")
        if normalized in {"sativa-hybrid", "sativa hybrid"}:
            return "Sativa-hybrid"
        if normalized in {"indica-hybrid", "indica hybrid"}:
            return "Indica-hybrid"
        if compact in {"50/50", "50-50", "50:50", "5050"} or "balanced" in normalized:
            return "50/50"
        return value


class IrrigationPlanPayload(StrictModel):
    enabled: bool = False
    every_n_days: int = Field(default=1, ge=1, le=365)
    offset_after_light_on_min: int = Field(default=0, ge=0, le=24 * 60)
    last_run_date: date | None = None


class ExhaustVpdPlanPayload(StrictModel):
    enabled: bool = False
    min_vpd_kpa: float = Field(default=0.6, ge=0, le=10)
    hysteresis_kpa: float = Field(default=0.05, ge=0, le=10)


class AirSensorSettings(StrictModel):
    enabled: bool = False
    host: str | None = Field(default=None, max_length=255)

    @field_validator("host", mode="before")
    @classmethod
    def strip_host(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None


class AirSensorCurrent(BaseModel):
    enabled: bool
    configured: bool
    ok: bool
    cached: bool
    temperature_c: float | None = None
    humidity_percent: float | None = None
    sds_p1: float | None = None
    sds_p2: float | None = None
    age_seconds: int | None = None
    software_version: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None


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
