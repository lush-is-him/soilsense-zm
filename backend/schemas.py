"""Request and response bodies (spec section 4)."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Language = Literal["en", "ny", "toi"]


class LoginIn(BaseModel):
    username: str
    password: str


Role = Literal["farmer", "officer", "admin"]
Phone = Optional[str]
PHONE_PATTERN = r"^\+?[0-9]{9,15}$"


class UserIn(BaseModel):
    """Admin creates an account (an officer, another admin, or a farmer)."""
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8)
    role: Role
    full_name: str = Field(min_length=2, max_length=80)


class UserPatch(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=80)
    role: Optional[Role] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class SignupIn(BaseModel):
    """A farmer creates their own account; the farmer profile is created with it."""
    full_name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8)
    village: Optional[str] = Field(None, max_length=80)
    preferred_language: Literal["en", "ny", "toi"] = "en"
    phone: Phone = Field(None, pattern=PHONE_PATTERN)
    sms_consent: bool = False
    share_consent: bool = False

    @model_validator(mode="after")
    def phone_needs_consent(self):
        if self.phone and not self.sms_consent:
            raise ValueError("a phone number may only be stored with SMS consent (NFR5)")
        return self


class FarmerIn(BaseModel):
    alias: str = Field(min_length=1, max_length=60)
    preferred_language: Language = "en"
    phone: Optional[str] = Field(None, pattern=r"^\+?[0-9]{9,15}$")
    sms_consent: bool = False
    village: Optional[str] = Field(None, max_length=80)
    share_consent: bool = False

    @model_validator(mode="after")
    def phone_needs_consent(self):
        if self.phone and not self.sms_consent:
            raise ValueError("a phone number may only be stored with SMS consent (NFR5)")
        return self


class FieldIn(BaseModel):
    farmer_id: Optional[int] = None      # a farmer adding their own field may leave it out
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
    point_label: Optional[str] = Field(None, max_length=20)    # a sampling point in the field, e.g. S04
    point_lat: Optional[float] = Field(None, ge=-90, le=90)
    point_lon: Optional[float] = Field(None, ge=-180, le=180)

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
    referral_id: Optional[int] = None


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
    whole_field: bool = False              # advice from the median of the field's sampling points


class FarmerPatch(BaseModel):
    alias: Optional[str] = Field(None, min_length=1, max_length=60)
    preferred_language: Optional[Language] = None
    phone: Optional[str] = Field(None, pattern=PHONE_PATTERN)
    sms_consent: Optional[bool] = None
    village: Optional[str] = Field(None, max_length=80)
    share_consent: Optional[bool] = None


class FieldPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    gps_accuracy_m: Optional[float] = Field(None, ge=0)
    location_source: Optional[Literal["gps", "manual"]] = None
    area_lima: Optional[float] = Field(None, gt=0)


class ReferralIn(BaseModel):
    field_id: int
    kind: Literal["lab", "visit"]
    reading_id: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=300)


class ReferralPatch(BaseModel):
    status: Optional[Literal["open", "in_progress", "done", "cancelled"]] = None
    note: Optional[str] = Field(None, max_length=500)
