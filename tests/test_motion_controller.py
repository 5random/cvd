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
    assert any(
        m == "Initialized motion detection controller with MOG2 algorithm" for m in messages
    )


@pytest.mark.asyncio
async def test_multi_frame_threshold_mode(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={
            "multi_frame_enabled": True,
            "multi_frame_method": "threshold",
            "multi_frame_window": 3,
            "multi_frame_threshold": 0.6,
        },
    )
    ctrl = MotionDetectionController("md", cfg)

    results = [
        MotionDetectionResult(True, 0, 0, 0, None, None, 0.9),
        MotionDetectionResult(False, 0, 0, 0, None, None, 0.2),
        MotionDetectionResult(False, 0, 0, 0, None, None, 0.1),
    ]

    async def fake_submit(*a, **k):
        return results.pop(0)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", fake_submit)

    await ctrl.start()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    await ctrl.process_image(frame, {})
    await ctrl.process_image(frame, {})
    res = await ctrl.process_image(frame, {})
    assert res.data.motion_detected is False
    await ctrl.stop()


@pytest.mark.asyncio
async def test_multi_frame_probability_mode(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={
            "multi_frame_enabled": True,
            "multi_frame_method": "probability",
            "multi_frame_decay": 0.5,
            "multi_frame_threshold": 0.2,
        },
    )
    ctrl = MotionDetectionController("md", cfg)

    results = [
        MotionDetectionResult(False, 0, 0, 0, None, None, 0.0),
        MotionDetectionResult(True, 0, 0, 0, None, None, 1.0),
        MotionDetectionResult(False, 0, 0, 0, None, None, 0.0),
    ]

    async def fake_submit(*a, **k):
        return results.pop(0)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", fake_submit)

    await ctrl.start()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    await ctrl.process_image(frame, {})
    await ctrl.process_image(frame, {})
    res = await ctrl.process_image(frame, {})
    assert res.data.motion_detected is True
    await ctrl.stop()
