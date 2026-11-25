"""Validated public and internal API data models."""

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ComplaintRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    complaint_number: Optional[Union[int, str]] = None
    description: str = Field(default="", max_length=5000)
    category_id: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=120)
    location_description: Optional[str] = Field(default=None, max_length=240)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    submitted_at: Optional[datetime] = None

    @field_validator("description", "category", "category_id", "location_description")
    @classmethod
    def normalize_safe_strings(cls, value):
        if value is None:
            return value
        return "".join(char for char in value if char in "\n\t" or ord(char) >= 32).strip()

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both be omitted")
        return self


class DuplicateAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complaint: ComplaintRecord
    candidates: List[ComplaintRecord] = Field(max_length=300)
    top_k: int = Field(default=20, ge=1, le=50)


class BatchDuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: List[ComplaintRecord] = Field(min_length=1, max_length=10)
    candidates: List[ComplaintRecord] = Field(max_length=300)
    top_k: int = Field(default=10, ge=1, le=30)


class HotspotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    complaints: List[ComplaintRecord] = Field(max_length=5000)
    epsilon_meters: float = Field(default=500.0, gt=0, le=50000)
    min_samples: int = Field(default=3, ge=2, le=100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category_id: Optional[str] = Field(default=None, max_length=100)
    density_medium_per_km2: float = Field(default=10.0, gt=0)
    density_high_per_km2: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def valid_window(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.density_high_per_km2 <= self.density_medium_per_km2:
            raise ValueError("high density threshold must exceed medium threshold")
        return self
