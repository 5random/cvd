import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'program'))

from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.controller_base import ControllerConfig

@pytest.mark.asyncio
async def test_motion_detection_on_black_frame(monkeypatch):
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)

    async def direct(func, *a, **k):
        return func(*a, **k)
    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    await ctrl.start()
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    result = await ctrl.process_image(frame, {})
    assert result.success
    assert "motion_detected" in result.data
    await ctrl.stop()
