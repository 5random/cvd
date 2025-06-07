import time

import pytest

from src.controllers.algorithms.reactor_state import ReactorStateController, ReactorState, ReactorAlarmType
from src.controllers.controller_base import ControllerConfig
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus

@pytest.mark.asyncio
async def test_reactor_state_transitions(monkeypatch):
    # suppress logging
    from src.controllers.algorithms import reactor_state as module
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(module, name):
            monkeypatch.setattr(module, name, lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="rs",
        controller_type="reactor_state",
        parameters={
            "idle_temp_max": 30.0,
            "processing_temp_min": 50.0,
            "processing_temp_max": 80.0,
            "alarm_temp_max": 90.0,
            "motion_required_for_processing": False,
            "min_state_duration": 0.0,
        },
    )
    ctrl = ReactorStateController("rs", cfg)

    def reading(temp):
        return SensorReading("t1", temp, time.time(), SensorStatus.OK)

    res1 = await ctrl.derive_state({"t1": reading(25)}, {}, {})
    assert res1.data.state == ReactorState.IDLE

    res2 = await ctrl.derive_state({"t1": reading(40)}, {}, {})
    assert res2.data.state == ReactorState.HEATING

    res3 = await ctrl.derive_state({"t1": reading(60)}, {}, {})
    assert res3.data.state == ReactorState.PROCESSING

    res4 = await ctrl.derive_state({"t1": reading(95)}, {}, {})
    assert ReactorAlarmType.OVERTEMPERATURE in res4.data.alarms
    assert res4.data.state == ReactorState.ALARM


@pytest.mark.asyncio
async def test_motion_metadata_multiple_controllers(monkeypatch):
    from src.controllers.algorithms import reactor_state as module
    monkeypatch.setattr(module, "info", lambda *a, **k: None)
    monkeypatch.setattr(module, "warning", lambda *a, **k: None)
    monkeypatch.setattr(module, "error", lambda *a, **k: None)
    monkeypatch.setattr(module, "debug", lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="rs",
        controller_type="reactor_state",
        parameters={
            "idle_temp_max": 30.0,
            "processing_temp_min": 50.0,
            "processing_temp_max": 80.0,
            "min_state_duration": 0.0,
        },
    )
    ctrl = ReactorStateController("rs", cfg)

    reading = SensorReading("t1", 60, time.time(), SensorStatus.OK)

    controller_outputs = {
        "other": {"motion_detected": False},
        "md": {
            "data": {"motion_detected": True},
            "metadata": {"controller_type": "motion_detection"},
        },
    }

    res = await ctrl.derive_state({"t1": reading}, controller_outputs, {})
    assert res.data.motion_detected is True
    assert res.data.state == ReactorState.PROCESSING
