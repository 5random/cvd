import asyncio
import numpy as np

import pytest

from src.controllers.controller_utils.controller_data_sources import (
    camera_capture_controller,
)
from src.controllers.controller_utils.controller_data_sources.camera_capture_controller import (
    CameraCaptureController,
)
from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.controller_base import ControllerConfig, ControllerInput


class DummyCapture:
    def __init__(self, index):
        self.index = index
        self.opened = True
        self.read_calls = 0

    def isOpened(self):
        return True

    def read(self):
        import numpy as np

        self.read_calls += 1
        if self.read_calls == 1:
            raise RuntimeError("read fail")
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        frame.fill(self.read_calls)
        return True, frame

    def set(self, prop, value):
        return True

    def release(self):
        self.opened = False


class DummyNoRead(DummyCapture):
    def read(self):
        return False, None


class DummyClosed(DummyCapture):
    def __init__(self, index):
        super().__init__(index)
        self.opened = False

    def isOpened(self):
        return False


async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_camera_capture_recovery(monkeypatch):
    from src.controllers.controller_utils import controller_data_sources

    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)
    monkeypatch.setattr(
        cap_module.cv2, "VideoCapture", lambda idx, backend=None: DummyCapture(idx)
    )
    monkeypatch.setattr(cap_module, "info", lambda *a, **k: None)
    monkeypatch.setattr(cap_module, "warning", lambda *a, **k: None)
    monkeypatch.setattr(cap_module, "error", lambda *a, **k: None)
    if hasattr(cap_module, "debug"):
        monkeypatch.setattr(cap_module, "debug", lambda *a, **k: None)

    # also suppress logging in controller_base
    import src.controllers.controller_base as controller_base

    for name in ["info", "warning", "error", "debug"]:
        if hasattr(controller_base, name):
            monkeypatch.setattr(controller_base, name, lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="cam",
        controller_type="camera_capture",
        parameters={"device_index": 0, "fps": 10, "capture_backend": 0},
    )
    controller = CameraCaptureController("cam", cfg)
    started = await controller.start()
    assert started
    await asyncio.sleep(0.3)
    frame = controller.get_output()
    assert isinstance(frame, np.ndarray)

    md_cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    md = MotionDetectionController("md", md_cfg)
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    result = await md.process(
        ControllerInput(controller_data={"cam": {"image": frame}})
    )
    assert result.success
    await md.stop()
    await md.cleanup()
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    await controller.cleanup()


@pytest.mark.asyncio
async def test_reinitialize_on_none(monkeypatch):
    from src.controllers.controller_utils import controller_data_sources

    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)
    first = DummyCapture(0)
    second = DummyCapture(0)
    monkeypatch.setattr(cap_module.cv2, "VideoCapture", lambda idx, backend=None: first)
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(cap_module, name):
            monkeypatch.setattr(cap_module, name, lambda *a, **k: None)
    import src.controllers.controller_base as controller_base

    for name in ["info", "warning", "error", "debug"]:
        if hasattr(controller_base, name):
            monkeypatch.setattr(controller_base, name, lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="cam",
        controller_type="camera_capture",
        parameters={"device_index": 0, "fps": 10, "capture_backend": 0},
    )
    controller = CameraCaptureController("cam", cfg)
    started = await controller.start()
    assert started
    controller._capture = None
    monkeypatch.setattr(
        cap_module.cv2, "VideoCapture", lambda idx, backend=None: second
    )
    await asyncio.sleep(0.2)
    assert controller._capture is second

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    md_cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    md = MotionDetectionController("md", md_cfg)
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    result = await md.process(
        ControllerInput(controller_data={"cam": {"image": frame}})
    )
    assert result.success
    await md.stop()
    await md.cleanup()
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    await controller.cleanup()


@pytest.mark.asyncio
async def test_reopen_after_failures(monkeypatch):
    from src.controllers.controller_utils import controller_data_sources

    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)
    attempts = {"count": 0}

    def video_capture(idx, backend=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return DummyCapture(idx)
        elif attempts["count"] <= 3:
            return DummyClosed(idx)
        else:
            return DummyCapture(idx)

    monkeypatch.setattr(cap_module.cv2, "VideoCapture", video_capture)
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(cap_module, name):
            monkeypatch.setattr(cap_module, name, lambda *a, **k: None)
    import src.controllers.controller_base as controller_base

    for name in ["info", "warning", "error", "debug"]:
        if hasattr(controller_base, name):
            monkeypatch.setattr(controller_base, name, lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="cam",
        controller_type="camera_capture",
        parameters={"device_index": 0, "fps": 10, "capture_backend": 0},
    )
    controller = CameraCaptureController("cam", cfg)
    started = await controller.start()
    assert started
    controller._capture = None
    await asyncio.sleep(0.8)
    assert attempts["count"] >= 3
    assert controller._capture is not None

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    md_cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    md = MotionDetectionController("md", md_cfg)
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    result = await md.process(
        ControllerInput(controller_data={"cam": {"image": frame}})
    )
    assert result.success
    await md.stop()
    await md.cleanup()
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    await controller.cleanup()
