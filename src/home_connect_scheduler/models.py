from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DayOfWeek(StrEnum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: float = 0.0


class ProgramOption(BaseModel):
    key: str
    value: bool | int | str
    unit: str | None = None


class Schedule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    day: DayOfWeek
    time: str  # HH:MM
    program: str
    options: list[ProgramOption] = Field(default_factory=list)
    enabled: bool = True


class RunResult(BaseModel):
    schedule_id: str
    schedule_name: str
    timestamp: datetime
    success: bool
    message: str = ""


class AppData(BaseModel):
    tokens: TokenData | None = None
    selected_appliance: str | None = None
    schedules: list[Schedule] = Field(default_factory=list)
    run_log: list[RunResult] = Field(default_factory=list)
