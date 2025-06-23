import numpy as np
import pytest
import asyncio
from PIL import Image
import cv2

from cvd.controllers.webcam import (
    MotionDetectionController,
    MotionDetectionResult,
)
from cvd.controllers.webcam.motion_detection import analyze_motion
from cvd.controllers.controller_base import ControllerConfig

messages: list[str] = []


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

    import cvd.controllers.webcam.motion_detection as md

    monkeypatch.setattr(md, "info", lambda msg, **kwargs: messages.append(msg))

    success = await ctrl.initialize()
    await ctrl.cleanup()

    assert success

    assert any(
        m == "Initialized motion detection controller with MOG2 algorithm"
        for m in messages
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

    assert any(m == "Motion detection controller initialized" for m in messages)


@pytest.mark.asyncio
async def test_multi_frame_probability_decay_influence(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={
            "multi_frame_enabled": True,
            "multi_frame_method": "probability",
            "multi_frame_decay": 0.9,
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
    assert res.data.motion_detected is False
    await ctrl.stop()


@pytest.mark.asyncio
async def test_bg_subtractor_mog2_params(monkeypatch):
    params = {
        "algorithm": "MOG2",
        "var_threshold": 12,
        "history": 321,
        "detect_shadows": False,
    }
    config = ControllerConfig(
        controller_id="md", controller_type="motion_detection", parameters=params
    )
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
    config = ControllerConfig(
        controller_id="md", controller_type="motion_detection", parameters=params
    )
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


def test_convert_to_cv_frame_bgr_passthrough():
    config = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", config)
    bgr = np.zeros((5, 5, 3), dtype=np.uint8)
    bgr[:, :, 0] = 10
    bgr[:, :, 1] = 20
    bgr[:, :, 2] = 30

    converted = ctrl._convert_to_cv_frame(bgr)
    assert np.array_equal(converted, bgr)


@pytest.mark.asyncio
async def test_stop_event_initialized_and_persistent():
    cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", cfg)
    assert isinstance(ctrl._stop_event, asyncio.Event)
    started = await ctrl.start()
    assert started
    assert isinstance(ctrl._stop_event, asyncio.Event)
    await ctrl.stop()


def test_multi_frame_window_defaults_to_one_on_zero():
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"multi_frame_window": 0},
    )
    ctrl = MotionDetectionController("md", cfg)
    assert ctrl.multi_frame_window == 1


def test_multi_frame_window_defaults_to_one_on_negative():
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"multi_frame_window": -5},
    )
    ctrl = MotionDetectionController("md", cfg)
    assert ctrl.multi_frame_window == 1


def test_motion_threshold_percentage_defaults_to_positive():
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"motion_threshold_percentage": 0},
    )
    ctrl = MotionDetectionController("md", cfg)
    assert ctrl.motion_threshold_percentage == 1.0


def test_analyze_motion_zero_threshold_confidence_zero():
    mask = np.zeros((10, 10), dtype=np.uint8)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    result = analyze_motion(
        mask,
        frame,
        min_contour_area=1,
        roundness_enabled=False,
        roundness_threshold=0.0,
        motion_threshold_percentage=0.0,
        confidence_threshold=0.5,
    )
    assert result.confidence == 0.0
    assert result.motion_detected is False


@pytest.mark.asyncio
async def test_invalid_roi_dimensions_skip_crop(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"roi_width": 0, "roi_height": -1},
    )
    ctrl = MotionDetectionController("md", cfg)

    async def direct(func, *a, **k):
        return func(*a, **k)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    import cvd.controllers.webcam.motion_detection as md

    warnings: list[str] = []
    monkeypatch.setattr(md, "warning", lambda msg, **kw: warnings.append(msg))

    await ctrl.start()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    result = await ctrl.process_image(frame, {})
    await ctrl.stop()

    assert result.success
    assert warnings
    assert ctrl.roi_width is None and ctrl.roi_height is None
    assert result.data.frame.shape == frame.shape


@pytest.mark.asyncio
async def test_roi_out_of_bounds_skip_crop(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"roi_width": 5, "roi_height": 5, "roi_x": 20, "roi_y": 20},
    )
    ctrl = MotionDetectionController("md", cfg)

    async def direct(func, *a, **k):
        return func(*a, **k)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    import cvd.controllers.webcam.motion_detection as md

    warnings: list[str] = []
    monkeypatch.setattr(md, "warning", lambda msg, **kw: warnings.append(msg))

    await ctrl.start()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    result = await ctrl.process_image(frame, {})
    await ctrl.stop()

    assert result.success
    assert warnings
    assert result.data.frame.shape == frame.shape

def test_invalid_gaussian_blur_kernel_defaults(monkeypatch):
    import cvd.controllers.webcam.motion_detection as md

    warnings: list[str] = []
    monkeypatch.setattr(md, "warning", lambda msg, **kw: warnings.append(msg))

    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"gaussian_blur_kernel": (4, 4)},
    )
    ctrl = MotionDetectionController("md", cfg)
    assert ctrl.gaussian_blur_kernel == (5, 5)
    assert warnings


def test_invalid_morphology_kernel_size_defaults(monkeypatch):
    import cvd.controllers.webcam.motion_detection as md

    warnings: list[str] = []
    monkeypatch.setattr(md, "warning", lambda msg, **kw: warnings.append(msg))

    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"morphology_kernel_size": 0},
    )
    ctrl = MotionDetectionController("md", cfg)
    assert ctrl.morphology_kernel_size == 5
    assert warnings

@pytest.mark.asyncio
async def test_frame_size_updates_on_roi_change(monkeypatch):
    cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", cfg)

    async def direct(func, *a, **k):
        return func(*a, **k)

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", direct)

    await ctrl.start()
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    result1 = await ctrl.process_image(frame, {})
    assert result1.metadata["frame_size"] == (20, 10)

    ctrl.roi_x = 5
    ctrl.roi_y = 0
    ctrl.roi_width = 10
    ctrl.roi_height = 10

    result2 = await ctrl.process_image(frame, {})
    await ctrl.stop()

    assert result2.metadata["frame_size"] == (10, 10)
    assert ctrl._frame_size == (10, 10)

async def test_roi_bbox_and_center_adjustment(monkeypatch):
    cfg = ControllerConfig(
        controller_id="md",
        controller_type="motion_detection",
        parameters={"roi_width": 5, "roi_height": 5, "roi_x": 3, "roi_y": 4},
    )
    ctrl = MotionDetectionController("md", cfg)

    async def fake_submit(*a, **k):
        return MotionDetectionResult(
            True,
            1.0,
            20.0,
            1,
            motion_center=(1, 1),
            motion_bbox=(0, 0, 2, 2),
            confidence=0.9,
        )

    monkeypatch.setattr(ctrl._motion_pool, "submit_async", fake_submit)

    await ctrl.start()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    result = await ctrl.process_image(frame, {})
    await ctrl.stop()

    assert result.success
    assert result.data.motion_bbox == (3, 4, 2, 2)
    assert result.data.motion_center == (4, 5)
    assert result.data.frame.shape[:2] == (5, 5)
