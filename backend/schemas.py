"""Request and response bodies (spec section 4)."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Language = Literal["en", "ny", "toi"]


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    role: Literal["operator", "agronomist", "admin"]


class FarmerIn(BaseModel):
    alias: str = Field(min_length=1, max_length=60)
    preferred_language: Language = "en"
    phone: Optional[str] = Field(None, pattern=r"^\+?[0-9]{9,15}$")
    sms_consent: bool = False

    @model_validator(mode="after")
    def phone_needs_consent(self):
        if self.phone and not self.sms_consent:
            raise ValueError("a phone number may only be stored with SMS consent (NFR5)")
        return self


class FieldIn(BaseModel):
    farmer_id: int
    name: str = Field(min_length=1, max_length=60)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    gps_accuracy_m: Optional[float] = Field(None, ge=0)
    location_source: Literal["gps", "manual"]
    area_lima: Optional[float] = Field(None, gt=0)


class DeviceIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=40)
    label: str


class CalibrationIn(BaseModel):
    """Electrode millivolts in each buffer, as measured by the bridge."""
    mv_ph7: float
    mv_ph4: float
    temp_c: float = Field(ge=0, le=50)


class ReadingIn(BaseModel):
    """Posted by the serial bridge (raw mV) or entered by the operator (pH)."""
    field_id: int
    device_id: Optional[str] = None
    replicates_mv: Optional[List[float]] = None
    replicates_ph: Optional[List[float]] = None
    moisture: Optional[float] = None
    temp_c: Optional[float] = None

    @model_validator(mode="after")
    def one_kind_of_replicates(self):
        if (self.replicates_mv is None) == (self.replicates_ph is None):
            raise ValueError("send exactly one of replicates_mv or replicates_ph")
        if self.replicates_mv is not None and not self.device_id:
            raise ValueError("replicates_mv needs a device_id (its calibration converts mV to pH)")
        return self


class FieldCheckIn(BaseModel):
    texture_by_feel: Optional[Literal["sandy", "loamy", "clay"]] = None
    colour: Optional[str] = None
    waterlogging: Optional[bool] = None
    previous_crop: Optional[str] = None
    manure_available: Optional[bool] = None


class LabResultIn(BaseModel):
    ph: float = Field(ge=2, le=11)
    ph_method: Literal["water", "cacl2"]
    soil_water_ratio: Optional[str] = "1:2.5"
    oc: Optional[float] = None
    p: Optional[float] = None
    k: Optional[float] = None
    texture: Optional[str] = None
    lab_name: Optional[str] = None
    date: Optional[str] = None


class AdviceIn(BaseModel):
    field_id: int
    reading_id: Optional[int] = None      # optional when a lab result exists
    crop: str
    budget_band: Literal["low", "medium"] = "low"
    water: Literal["rainfed", "irrigated"] = "rainfed"
    previous_crop: Optional[str] = None
    manure_available: Optional[bool] = None
    as_of_date: Optional[date] = None      # defaults to today; set in tests
    lang: Language = "en"
