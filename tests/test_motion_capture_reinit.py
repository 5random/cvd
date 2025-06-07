import asyncio
import numpy as np
import pytest

from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.controller_base import ControllerConfig, ControllerInput

async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)

@pytest.mark.asyncio
async def test_process_from_controller_data(monkeypatch):
    cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    controller = MotionDetectionController("md", cfg)
    monkeypatch.setattr(controller._motion_pool, "submit_async", immediate)
    started = await controller.start()
    assert started

    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    result = await controller.process(ControllerInput(controller_data={"cam": {"image": frame}}))
    assert result.success
    await controller.stop()
    await controller.cleanup()
