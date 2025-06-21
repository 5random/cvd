
import time
from datetime import datetime
import pytest

from program.src.data_handler.interface.sensor_interface import SensorReading, SensorStatus
from program.src.experiment_handler import experiment_manager as em_module
from program.src.experiment_handler.experiment_manager import (
    ExperimentManager,
    ExperimentResult,
    ExperimentPhase,
    ExperimentState,
)


class DummyConfigService:
    def get(self, *args, **kwargs):
        return kwargs.get("default")


class DummySensorManager:
    def get_latest_readings(self):
        return {"s1": SensorReading("s1", 1.0, time.time(), SensorStatus.OK)}


class DummyControllerManager:
    def get_controller_outputs(self):
        return {"c1": {"value": 42}}


@pytest.mark.asyncio
async def test_collect_data_point_includes_controller_outputs(monkeypatch):
    monkeypatch.setattr(em_module, "get_compression_service", lambda: None)

    manager = ExperimentManager(
        DummyConfigService(), DummySensorManager(), DummyControllerManager(), None
    )
    manager._current_experiment = "exp1"
    manager._current_phase = ExperimentPhase.PROCESSING
    manager._experiment_results["exp1"] = ExperimentResult(
        experiment_id="exp1",
        name="exp",
        state=ExperimentState.RUNNING,
        start_time=datetime.now(),
    )

    await manager._collect_data_point()

    assert manager._collected_data
    dp = manager._collected_data[-1]
    assert dp.controller_outputs == {"c1": {"value": 42}}

