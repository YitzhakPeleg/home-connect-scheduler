import stat
from datetime import UTC
from pathlib import Path
from unittest.mock import patch

from home_connect_scheduler.models import (
    AppData,
    DayOfWeek,
    RunResult,
    Schedule,
    TokenData,
)
from home_connect_scheduler.store import MAX_RUN_LOG, load, save


class TestStore:
    def setup_method(self):
        self._tmp_dir = None

    def _patch_paths(self, tmp_path: Path):
        data_dir = tmp_path / ".hcs"
        data_file = data_dir / "data.json"
        return (
            patch("home_connect_scheduler.store.DATA_DIR", data_dir),
            patch("home_connect_scheduler.store.DATA_FILE", data_file),
        )

    def test_load_empty(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            data = load()
            assert data == AppData()

    def test_save_and_load_round_trip(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            data = AppData(
                tokens=TokenData(access_token="tok", refresh_token="ref"),
                selected_appliance="BOSCH-123",
                schedules=[
                    Schedule(
                        name="eco",
                        day=DayOfWeek.SAT,
                        time="01:00",
                        program="Dishcare.Program.Eco50",
                    )
                ],
            )
            save(data)
            loaded = load()
            assert loaded.tokens.access_token == "tok"
            assert loaded.selected_appliance == "BOSCH-123"
            assert len(loaded.schedules) == 1

    def test_run_log_trimming(self, tmp_path):
        from datetime import datetime

        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            data = AppData(
                run_log=[
                    RunResult(
                        schedule_id="x",
                        schedule_name="test",
                        timestamp=datetime.now(tz=UTC),
                        success=True,
                        message=f"run {i}",
                    )
                    for i in range(MAX_RUN_LOG + 20)
                ]
            )
            save(data)
            loaded = load()
            assert len(loaded.run_log) == MAX_RUN_LOG
            # Should keep the most recent entries
            assert loaded.run_log[-1].message == f"run {MAX_RUN_LOG + 19}"

    def test_file_permissions(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            save(AppData())
            data_file = tmp_path / ".hcs" / "data.json"
            mode = data_file.stat().st_mode
            assert stat.S_IMODE(mode) == 0o600
