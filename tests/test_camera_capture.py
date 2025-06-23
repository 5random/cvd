import asyncio
import numpy as np

import pytest
import cv2

from cvd.controllers.webcam import CameraCaptureController, MotionDetectionController
from cvd.controllers.controller_base import ControllerConfig, ControllerInput


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


class DummyProbeCapture(DummyCapture):
    def __init__(self, index, width=None, height=None, fps=None):
        super().__init__(index)
        self.width = width
        self.height = height
        self.fps = fps

    def set(self, prop, value):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            self.width = int(value)
        elif prop == cv2.CAP_PROP_FRAME_HEIGHT:
            self.height = int(value)
        elif prop == cv2.CAP_PROP_FPS:
            self.fps = int(value)
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width or 0
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height or 0
        if prop == cv2.CAP_PROP_FPS:
            return self.fps or 0
        return 0


async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_camera_capture_recovery(monkeypatch):
    from cvd.controllers import webcam as controller_data_sources

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
    import cvd.controllers.controller_base as controller_base

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
    md.config.input_controllers = ["cam"]
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    assert md._capture_task is None
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
async def test_probe_camera_modes_single_capture(monkeypatch):
    from src.controllers import camera_utils

    open_count = {"count": 0}

    async def dummy_open(device_index, width, height, fps, capture_backend=None):
        open_count["count"] += 1
        return DummyProbeCapture(device_index, width, height, fps)

    monkeypatch.setattr(camera_utils, "open_capture", dummy_open)
    monkeypatch.setattr(camera_utils, "run_camera_io", immediate)

    modes = await camera_utils.probe_camera_modes(device_index=0)
    assert open_count["count"] == 1
    assert modes


@pytest.mark.asyncio
async def test_reinitialize_on_none(monkeypatch):
    from cvd.controllers import webcam as controller_data_sources

    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)
    first = DummyCapture(0)
    second = DummyCapture(0)
    monkeypatch.setattr(cap_module.cv2, "VideoCapture", lambda idx, backend=None: first)
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(cap_module, name):
            monkeypatch.setattr(cap_module, name, lambda *a, **k: None)
    import cvd.controllers.controller_base as controller_base

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
    md.config.input_controllers = ["cam"]
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    assert md._capture_task is None
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
    from cvd.controllers import webcam as controller_data_sources

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
    import cvd.controllers.controller_base as controller_base

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
    md.config.input_controllers = ["cam"]
    monkeypatch.setattr(md._motion_pool, "submit_async", immediate)
    await md.start()
    assert md._capture_task is None
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
async def test_backend_fallback(monkeypatch):
    from cvd.controllers import webcam as controller_data_sources

    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)

    primary = DummyClosed(0)
    secondary = DummyCapture(0)

    def video_capture(idx, backend=None):
        if backend in (None, 0):
            return primary
        return secondary

    monkeypatch.setattr(cap_module.cv2, "VideoCapture", video_capture)
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(cap_module, name):
            monkeypatch.setattr(cap_module, name, lambda *a, **k: None)
    import cvd.controllers.controller_base as controller_base

    for name in ["info", "warning", "error", "debug"]:
        if hasattr(controller_base, name):
            monkeypatch.setattr(controller_base, name, lambda *a, **k: None)

    cfg = ControllerConfig(
        controller_id="cam",
        controller_type="camera_capture",
        parameters={
            "device_index": 0,
            "fps": 10,
            "capture_backend": 0,
            "capture_backend_fallbacks": [1],
        },
    )
    controller = CameraCaptureController("cam", cfg)
    started = await controller.start()
    assert started
    assert controller._capture is secondary
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    await controller.cleanup()
