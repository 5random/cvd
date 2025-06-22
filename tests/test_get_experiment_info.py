from datetime import datetime

from src.gui.gui_tab_components.gui_tab_experiment_component import (
    CurrentExperimentDisplay,
)
from src.experiment_manager import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentState,
    ExperimentPhase,
)


class DummySensorManager:
    def __init__(self, active, all_):
        self._active = list(active)
        self._all = list(all_)

    def get_active_sensors(self):
        return list(self._active)

    def get_all_sensors(self):
        return list(self._all)


class DummyControllerManager:
    def __init__(self, ids):
        self._ids = list(ids)

    def list_controllers(self):
        return list(self._ids)


class DummyExperimentManager:
    def __init__(self, config, result, sensor_mgr=None, controller_mgr=None):
        self._config = config
        self._result = result
        self.sensor_manager = sensor_mgr
        self.controller_manager = controller_mgr

    def get_experiment_config(self, eid):
        return self._config if eid == "exp1" else None

    def get_experiment_result(self, eid):
        return self._result if eid == "exp1" else None

    def get_current_state(self):
        return ExperimentState.RUNNING

    def get_current_phase(self):
        return ExperimentPhase.PROCESSING


def create_display(active, all_s, controllers):
    cfg = ExperimentConfig(name="exp", sensor_ids=[], controller_ids=[])
    res = ExperimentResult(
        experiment_id="exp1",
        name="exp",
        state=ExperimentState.RUNNING,
        start_time=datetime.now(),
    )
    sensor_mgr = DummySensorManager(active, all_s)
    ctrl_mgr = DummyControllerManager(controllers)
    mgr = DummyExperimentManager(cfg, res, sensor_mgr, ctrl_mgr)
    return CurrentExperimentDisplay(mgr)


def test_get_experiment_info_active_counts():
    disp = create_display(["s1", "s2"], ["s1", "s2", "s3"], ["c1", "c2"])
    info = disp._get_experiment_info("exp1")
    assert info.sensor_count == 2
    assert info.controller_count == 2


def test_get_experiment_info_fallback_all():
    disp = create_display([], ["s1", "s2", "s3"], ["c1"])
    info = disp._get_experiment_info("exp1")
    assert info.sensor_count == 3
    assert info.controller_count == 1

