import json
import pytest

from src.utils.config_utils.config_service import ConfigurationService
from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import (
    ControllerStage,
    ControllerConfig,
    ControllerInput,
    ControllerResult,
    ControllerStatus,
)
from src.experiment_handler.experiment_manager import ExperimentManager


class DummyController(ControllerStage):
    def __init__(self, cid: str):
        cfg = ControllerConfig(controller_id=cid, controller_type="dummy")
        super().__init__(cid, cfg)

    async def process(self, input_data: ControllerInput) -> ControllerResult:
        return ControllerResult.success_result(None)

    async def initialize(self) -> bool:
        return True

    async def start(self):
        started.append(self.controller_id)
        return await super().start()


def create_service(tmp_path, cfg=None):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg or {}))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


@pytest.mark.asyncio
async def test_start_selected_controllers(tmp_path):
    service = create_service(tmp_path)
    ctrl_mgr = ControllerManager("test")

    global started
    started = []
    c1 = DummyController("c1")
    c2 = DummyController("c2")
    ctrl_mgr.register_controller(c1)
    ctrl_mgr.register_controller(c2)

    manager = ExperimentManager(service, controller_manager=ctrl_mgr)

    await manager._start_controllers(["c1"])

    assert started == ["c1"]
    assert c1.status == ControllerStatus.RUNNING
    assert c2.status == ControllerStatus.STOPPED


class FailController(DummyController):
    async def start(self):
        started.append(self.controller_id)
        return False


@pytest.mark.asyncio
async def test_start_controllers_with_failure(tmp_path):
    service = create_service(tmp_path)
    ctrl_mgr = ControllerManager("test")

    global started
    started = []
    c1 = FailController("bad")
    c2 = DummyController("good")
    ctrl_mgr.register_controller(c1)
    ctrl_mgr.register_controller(c2)

    manager = ExperimentManager(service, controller_manager=ctrl_mgr)

    await manager._start_controllers(["bad", "good"])

    assert started == ["bad", "good"]
    assert c1.status == ControllerStatus.STOPPED
    assert c2.status == ControllerStatus.RUNNING
