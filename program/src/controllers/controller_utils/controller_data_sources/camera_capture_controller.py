"""Camera capture controller using OpenCV and thread pool"""

import cv2
import asyncio
import contextlib
from typing import Optional

from src.utils.concurrency.thread_pool import run_camera_io
from src.utils.config_utils.config_service import get_config_service
from src.controllers.controller_base import (
    ControllerStage,
    ControllerConfig,
    ControllerType,
    ControllerInput,
    ControllerResult,
)
from src.utils.log_utils.log_service import info, warning, error
from src.controllers.controller_utils.camera_utils import (
    apply_uvc_settings,
    rotate_frame,
)


class CameraCaptureController(ControllerStage):
    """Controller that captures frames from a camera using cv2.VideoCapture."""

    def __init__(
        self,
        controller_id: str = "camera_capture",
        config: Optional[ControllerConfig] = None,
    ):
        if config is None:
            config = ControllerConfig(
                controller_id=controller_id, controller_type="camera_capture"
            )
        super().__init__(controller_id, config)
        self.controller_type = ControllerType.CUSTOM

        params = config.parameters
        self.device_index = params.get("device_index", 0)
        self.width = params.get("width")
        self.height = params.get("height")
        self.fps = params.get("fps")
        self.webcam_id = params.get("cam_id")
        self.rotation = params.get("rotation", 0)
        self.uvc_settings = params.get("uvc_settings", {})

        if self.webcam_id:

            service = get_config_service()
            if service:
                cam_cfg = service.get_webcam_config(self.webcam_id)
                if cam_cfg:
                    self.device_index = cam_cfg.get("device_index", self.device_index)
                    res = cam_cfg.get("resolution")
                    if res and len(res) == 2:
                        self.width, self.height = res
                    self.fps = cam_cfg.get("fps", self.fps)
                    self.rotation = cam_cfg.get("rotation", self.rotation)
                    self.uvc_settings.update(cam_cfg.get("uvc_settings", {}))

        self._capture: Optional[cv2.VideoCapture] = None
        self._capture_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def initialize(self) -> bool:
        """Initialize camera capture using the camera I/O thread pool."""
        try:
            self._capture = await run_camera_io(cv2.VideoCapture, self.device_index)
            if not self._capture or not self._capture.isOpened():
                error(
                    "Unable to open camera",
                    controller_id=self.controller_id,
                    device_index=self.device_index,
                )
                return False

            if self.width:
                await run_camera_io(
                    self._capture.set, cv2.CAP_PROP_FRAME_WIDTH, int(self.width)
                )
            if self.height:
                await run_camera_io(
                    self._capture.set, cv2.CAP_PROP_FRAME_HEIGHT, int(self.height)
                )
            if self.fps:
                await run_camera_io(self._capture.set, cv2.CAP_PROP_FPS, int(self.fps))
            await apply_uvc_settings(
                self._capture,
                self.uvc_settings,
                controller_id=self.controller_id,
            )
            return True
        except Exception as e:
            error(
                "Failed to initialize camera",
                controller_id=self.controller_id,
                device_index=self.device_index,
                error=str(e),
            )
            return False

    async def _capture_loop(self) -> None:
        base_delay = 1.0 / self.fps if self.fps else 0.03
        failure_delay = 0.1
        reopen_delay = 5.0
        failure_count = 0
        max_failures = 5
        delay = base_delay

        while not self._stop_event.is_set():
            try:
                if self._capture is None:
                    warning(
                        "Camera capture missing, attempting reinitialization",
                        controller_id=self.controller_id,
                        device_index=self.device_index,
                    )
                    try:
                        self._capture = await run_camera_io(
                            cv2.VideoCapture, self.device_index
                        )
                        if self._capture and self._capture.isOpened():
                            await apply_uvc_settings(
                                self._capture,
                                self.uvc_settings,
                                controller_id=self.controller_id,
                            )
                            failure_count = 0
                            delay = base_delay
                        else:
                            raise RuntimeError("capture not opened")
                    except Exception as exc:
                        error(
                            "Failed to reinitialize camera",
                            controller_id=self.controller_id,
                            device_index=self.device_index,
                            error=str(exc),
                        )
                        self._capture = None
                        failure_count += 1
                        if failure_count >= max_failures:
                            error(
                                "Camera unavailable, retrying later",
                                controller_id=self.controller_id,
                                device_index=self.device_index,
                            )
                            delay = reopen_delay
                            failure_count = 0
                        else:
                            delay = min(failure_delay * 2**failure_count, 2.0)
                    await asyncio.sleep(delay)
                    continue
                ret, frame = await run_camera_io(self._capture.read)
                if ret:
                    if self.rotation:
                        frame = rotate_frame(frame, self.rotation)
                    self._output_cache[self.controller_id] = frame
                    failure_count = 0
                    delay = base_delay
                else:
                    failure_count += 1
                    delay = min(failure_delay * 2**failure_count, 2.0)
                    if failure_count > max_failures:
                        opened = await run_camera_io(self._capture.isOpened)
                        if not opened:
                            warning(
                                "Camera not opened, reinitializing",
                                controller_id=self.controller_id,
                                device_index=self.device_index,
                            )
                            await run_camera_io(self._capture.release)
                            self._capture = None
                            continue
            except Exception as e:
                error(
                    "Camera capture error",
                    controller_id=self.controller_id,
                    device_index=self.device_index,
                    error=str(e),
                )
                failure_count += 1
                delay = min(failure_delay * 2**failure_count, 2.0)
            await asyncio.sleep(delay)

    async def start(self) -> bool:
        """Start capturing frames."""
        if not await super().start():
            return False
        self._stop_event.clear()
        self._capture_task = asyncio.create_task(self._capture_loop())
        info(
            "Camera capture started",
            controller_id=self.controller_id,
            device_index=self.device_index,
        )
        return True

    async def stop(self) -> None:
        """Stop capturing frames and release resources."""
        self._stop_event.set()
        if self._capture_task:
            self._capture_task.cancel()
            with contextlib.suppress(Exception):
                await self._capture_task
            self._capture_task = None
        await super().stop()

    async def cleanup(self) -> None:
        if self._capture is not None:
            await run_camera_io(self._capture.release)
            self._capture = None
        await super().cleanup()

    async def process(self, input_data: ControllerInput) -> ControllerResult:
        """Return the latest captured frame."""
        frame = self._output_cache.get(self.controller_id)
        if frame is None:
            return ControllerResult.success_result(None)
        return ControllerResult.success_result({"frame": frame})
