import numpy as np
import pytest

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


def test_convert_bgr_frame_unchanged():
    """Ensure that BGR frames are not converted to RGB."""
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)
    frame = np.random.randint(0, 256, (10, 10, 3), dtype=np.uint8)
    converted = ctrl._convert_to_cv_frame(frame)
    assert np.array_equal(converted, frame)
