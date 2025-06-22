import time
from datetime import datetime
import asyncio
import pytest

from src.data_handler.interface.sensor_interface import (
    SensorReading,
    SensorStatus,
)
from src import experiment_manager as em_module
from src.experiment_manager import (
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


@pytest.mark.asyncio
async def test_auto_stop_task_cancelled_on_manual_stop(monkeypatch):
    monkeypatch.setattr(em_module, "get_compression_service", lambda: None)

    manager = ExperimentManager(
        DummyConfigService(), DummySensorManager(), DummyControllerManager(), None
    )

    cfg = em_module.ExperimentConfig(
        name="exp",
        duration_minutes=1,
        auto_start_sensors=False,
        auto_start_controllers=False,
    )
    eid = manager.create_experiment(cfg)

    started = await manager.start_experiment(eid)
    assert started

    await asyncio.sleep(0.01)
    await manager.stop_experiment()

    assert manager._auto_stop_handle is None
    assert "auto_stop" not in manager._task_manager._tasks
