import numpy as np
import pytest
from PIL import Image
import cv2

from src.controllers.algorithms.motion_detection import (
    MotionDetectionController,
    MotionDetectionResult,
)
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
    assert isinstance(result.data, MotionDetectionResult)
    await ctrl.stop()


@pytest.mark.asyncio
async def test_motion_detection_on_pil_image(monkeypatch):
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)

    async def direct(func, *a, **k):
        return func(*a, **k)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    await ctrl.start()
    np_frame = np.zeros((50, 50, 3), dtype=np.uint8)
    pil_image = Image.fromarray(np_frame)
    result = await ctrl.process_image(pil_image, {})
    assert result.success
    assert isinstance(result.data, MotionDetectionResult)
    await ctrl.stop()


@pytest.mark.asyncio
async def test_motion_detection_on_bytes(monkeypatch):
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)

    async def direct(func, *a, **k):
        return func(*a, **k)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    await ctrl.start()
    np_frame = np.zeros((50, 50, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", np_frame)
    bytes_data = encoded.tobytes()
    result = await ctrl.process_image(bytes_data, {})
    assert result.success
    assert isinstance(result.data, MotionDetectionResult)
    await ctrl.stop()


@pytest.mark.asyncio
async def test_initialize_logs_algorithm(monkeypatch):
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)

    import src.controllers.algorithms.motion_detection as md
    messages = []
    monkeypatch.setattr(md, "info", lambda msg, **kwargs: messages.append(msg))

    success = await ctrl.initialize()
    await ctrl.cleanup()

    assert success
    assert any(m == "Motion detection controller initialized" for m in messages)


@pytest.mark.asyncio
async def test_bg_subtractor_mog2_params(monkeypatch):
    params = {
        "algorithm": "MOG2",
        "var_threshold": 12,
        "history": 321,
        "detect_shadows": False,
    }
    config = ControllerConfig(controller_id="md", controller_type="motion_detection", parameters=params)
    ctrl = MotionDetectionController("md", config)

    called = {}

    def fake_mog2(*, detectShadows=True, varThreshold=16, history=500):
        called["detectShadows"] = detectShadows
        called["varThreshold"] = varThreshold
        called["history"] = history

        class Dummy:
            def apply(self, *a, **k):
                return np.zeros((1, 1), dtype=np.uint8)

        return Dummy()

    monkeypatch.setattr(cv2, "createBackgroundSubtractorMOG2", fake_mog2)

    success = await ctrl.initialize()
    await ctrl.cleanup()

    assert success
    assert called == {"detectShadows": False, "varThreshold": 12, "history": 321}


@pytest.mark.asyncio
async def test_bg_subtractor_knn_params(monkeypatch):
    params = {
        "algorithm": "KNN",
        "dist2_threshold": 42.0,
        "history": 111,
        "detect_shadows": False,
    }
    config = ControllerConfig(controller_id="md", controller_type="motion_detection", parameters=params)
    ctrl = MotionDetectionController("md", config)

    called = {}

    def fake_knn(*, detectShadows=True, dist2Threshold=400.0, history=500):
        called["detectShadows"] = detectShadows
        called["dist2Threshold"] = dist2Threshold
        called["history"] = history

        class Dummy:
            def apply(self, *a, **k):
                return np.zeros((1, 1), dtype=np.uint8)

        return Dummy()

    monkeypatch.setattr(cv2, "createBackgroundSubtractorKNN", fake_knn)

    success = await ctrl.initialize()
    await ctrl.cleanup()

    assert success
    assert called == {
        "detectShadows": False,
        "dist2Threshold": 42.0,
        "history": 111,
    }
