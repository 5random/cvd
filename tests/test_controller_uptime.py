import asyncio
import pytest

from cvd.controllers.controller_base import ControllerStage, ControllerConfig, ControllerResult

class DummyController(ControllerStage):
    async def process(self, input_data):
        return ControllerResult.success_result(None)

    async def initialize(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

@pytest.mark.asyncio
async def test_uptime_tracking():
    cfg = ControllerConfig(controller_id="d1", controller_type="custom")
    ctrl = DummyController("d1", cfg)
    await ctrl.start()
    stats = ctrl.get_stats()
    assert stats["start_time"] is not None
    await asyncio.sleep(0.05)
    stats = ctrl.get_stats()
    assert stats["uptime_s"] is not None and stats["uptime_s"] > 0
    await ctrl.stop()
    stats = ctrl.get_stats()
    assert stats["start_time"] is None

