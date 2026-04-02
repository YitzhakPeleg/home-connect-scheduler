import pytest
from pydantic import ValidationError

from home_connect_scheduler.models import (
    AppData,
    DayOfWeek,
    ProgramOption,
    Schedule,
    TokenData,
)


class TestTokenData:
    def test_valid(self):
        t = TokenData(access_token="abc", refresh_token="def", expires_at=1000.0)
        assert t.access_token == "abc"
        assert t.refresh_token == "def"
        assert t.expires_at == 1000.0

    def test_defaults(self):
        t = TokenData(access_token="a", refresh_token="b")
        assert t.expires_at == 0.0


class TestSchedule:
    def test_valid(self):
        s = Schedule(name="test", day=DayOfWeek.SAT, time="01:00", program="Dishcare.Program.Eco50")
        assert s.name == "test"
        assert s.enabled is True
        assert len(s.id) == 8

    def test_with_options(self):
        s = Schedule(
            name="test",
            day=DayOfWeek.SAT,
            time="14:00",
            program="Dishcare.Program.Auto2",
            options=[ProgramOption(key="Dishcare.Option.BrillianceDry", value=True)],
        )
        assert len(s.options) == 1
        assert s.options[0].value is True

    def test_invalid_day(self):
        with pytest.raises(ValidationError):
            Schedule(name="x", day="invalid", time="01:00", program="x")


class TestProgramOption:
    def test_bool_value(self):
        o = ProgramOption(key="k", value=True)
        assert o.unit is None

    def test_int_value_with_unit(self):
        o = ProgramOption(key="k", value=3600, unit="seconds")
        assert o.value == 3600
        assert o.unit == "seconds"


class TestAppData:
    def test_defaults(self):
        d = AppData()
        assert d.tokens is None
        assert d.selected_appliance is None
        assert d.schedules == []
        assert d.run_log == []

    def test_json_round_trip(self):
        d = AppData(
            tokens=TokenData(access_token="a", refresh_token="b"),
            selected_appliance="BOSCH-123",
            schedules=[Schedule(name="s", day=DayOfWeek.MON, time="08:00", program="p")],
        )
        dumped = d.model_dump(mode="json")
        restored = AppData.model_validate(dumped)
        assert restored.tokens.access_token == "a"
        assert restored.selected_appliance == "BOSCH-123"
        assert len(restored.schedules) == 1


class TestDayOfWeek:
    def test_all_days(self):
        assert len(DayOfWeek) == 7
        assert DayOfWeek.SAT.value == "sat"
