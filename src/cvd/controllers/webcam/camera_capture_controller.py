"""Camera capture controller using OpenCV and thread pool"""

import cv2
import asyncio
import contextlib
from typing import Optional, Any

from cvd.utils.concurrency.thread_pool import run_camera_io
from cvd.controllers.camera_utils import apply_uvc_settings
from cvd.utils.config_service import get_config_service
from cvd.controllers.controller_base import (
    ControllerStage,
    ControllerConfig,
    ControllerType,
    ControllerInput,
    ControllerResult,
)
from cvd.utils.log_service import info, warning, error
from .base_camera_capture import BaseCameraCapture


class CameraCaptureController(BaseCameraCapture, ControllerStage):
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
        self.capture_backend = params.get("capture_backend")
        self.capture_backend_fallbacks = params.get("capture_backend_fallbacks", [])
        self.webcam_id = params.get("cam_id")
        self.rotation = params.get("rotation", 0)
        self.uvc_settings = {}
        self.uvc_settings.update(params.get("uvc", {}))
        self.uvc_settings.update(params.get("uvc_settings", {}))

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
                    self.capture_backend = cam_cfg.get(
                        "capture_backend", self.capture_backend
                    )
                    self.capture_backend_fallbacks = cam_cfg.get(
                        "capture_backend_fallbacks", self.capture_backend_fallbacks
                    )
                    self.uvc_settings.update(cam_cfg.get("uvc", {}))
                    self.uvc_settings.update(cam_cfg.get("uvc_settings", {}))

    async def initialize(self) -> bool:
        """Initialize camera capture using the camera I/O thread pool."""
        opened = await self._open_capture()
        if not opened:
            error(
                "Unable to open camera",
                controller_id=self.controller_id,
                device_index=self.device_index,
            )
        return opened

    async def handle_frame(self, frame: Any) -> None:
        """Store the latest captured frame."""
        self._output_cache[self.controller_id] = frame

    async def start(self) -> bool:
        """Start capturing frames."""
        if not await super().start():
            return False
        self.start_capture()
        return True

    async def stop(self) -> None:
        """Stop capturing frames and release resources."""
        await self.stop_capture()
        await super().stop()

    async def cleanup(self) -> None:
        await self.cleanup_capture()
        await super().cleanup()

    async def process(self, input_data: ControllerInput) -> ControllerResult:
        """Return the latest captured frame."""
        frame = self._output_cache.get(self.controller_id)
        if frame is None:
            return ControllerResult.success_result(None)
        return ControllerResult.success_result({"frame": frame})

    async def apply_uvc_settings(
        self, settings: Optional[dict[str, Any]] | None = None
    ) -> None:
        """Apply UVC settings to the underlying capture device."""
        if settings:
            self.uvc_settings.update(settings)
        if self._capture is not None:
            await apply_uvc_settings(
                self._capture,
                self.uvc_settings if settings is None else settings,
                controller_id=self.controller_id,
            )

    async def test_camera_access(self) -> bool:
        """Quickly check if the configured camera can be accessed."""
        cap = None
        try:
            if self.capture_backend is not None:
                cap = await run_camera_io(
                    cv2.VideoCapture, self.device_index, self.capture_backend
                )
            else:
                cap = await run_camera_io(cv2.VideoCapture, self.device_index)
            if not cap or not await run_camera_io(cap.isOpened):
                if cap is not None:
                    await run_camera_io(cap.release)
                return False
            ret, _ = await run_camera_io(cap.read)
            await run_camera_io(cap.release)
            return bool(ret)
        except Exception:
            if cap is not None:
                with contextlib.suppress(Exception):
                    await run_camera_io(cap.release)
            return False
