"""Shared webcam capture loop utilities."""

from __future__ import annotations

import asyncio
import contextlib
from abc import ABC, abstractmethod
from typing import Optional, Any

import cv2

from ..camera_utils import apply_uvc_settings, rotate_frame
from cvd.utils.concurrency.thread_pool import run_camera_io
from cvd.utils.log_service import info, warning, error


class BaseCameraCapture(ABC):
    """Mixin providing a reusable camera capture loop."""

    def __init__(self, controller_id: str, config):
        super().__init__(controller_id, config)
        self.controller_id = controller_id
        self.config = config
        self._capture: Optional[cv2.VideoCapture] = None
        self._capture_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Hooks for subclasses
    @abstractmethod
    async def handle_frame(self, frame: Any) -> None:
        """Handle a captured frame."""
        raise NotImplementedError

    async def on_capture_opened(self) -> None:
        """Called when a capture device has been (re)opened."""
        return None

    # ------------------------------------------------------------------
    async def _open_capture(self) -> bool:
        try:
            if getattr(self, "capture_backend", None) is not None:
                self._capture = await run_camera_io(
                    cv2.VideoCapture, self.device_index, self.capture_backend
                )
            else:
                self._capture = await run_camera_io(cv2.VideoCapture, self.device_index)
            if not self._capture or not self._capture.isOpened():
                if self._capture is not None:
                    await run_camera_io(self._capture.release)
                self._capture = None
                return False
            if getattr(self, "width", None):
                await run_camera_io(
                    self._capture.set, cv2.CAP_PROP_FRAME_WIDTH, int(self.width)
                )
            if getattr(self, "height", None):
                await run_camera_io(
                    self._capture.set, cv2.CAP_PROP_FRAME_HEIGHT, int(self.height)
                )
            if getattr(self, "fps", None):
                await run_camera_io(self._capture.set, cv2.CAP_PROP_FPS, int(self.fps))
            await apply_uvc_settings(
                self._capture, self.uvc_settings, controller_id=self.controller_id
            )
            await self.on_capture_opened()
            return True
        except Exception as exc:  # pragma: no cover - defensive
            error(
                "Failed to initialize camera",
                controller_id=self.controller_id,
                device_index=getattr(self, "device_index", "unknown"),
                error=str(exc),
            )
            if self._capture is not None:
                with contextlib.suppress(Exception):
                    await run_camera_io(self._capture.release)
            self._capture = None
            return False

    # ------------------------------------------------------------------
    async def _capture_loop(self) -> None:
        base_delay = 1.0 / self.fps if getattr(self, "fps", None) else 0.03
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
                    opened = await self._open_capture()
                    if opened:
                        failure_count = 0
                        delay = base_delay
                    else:
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
                    if getattr(self, "rotation", 0):
                        frame = rotate_frame(frame, self.rotation)
                    await self.handle_frame(frame)
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
            except Exception as e:  # pragma: no cover - defensive
                error(
                    "Camera capture error",
                    controller_id=self.controller_id,
                    device_index=self.device_index,
                    error=str(e),
                )
                failure_count += 1
                delay = min(failure_delay * 2**failure_count, 2.0)
            await asyncio.sleep(delay)

    # Public helpers ---------------------------------------------------
    def start_capture(self) -> None:
        if self._capture_task and not self._capture_task.done():
            # Capture loop already running
            return

        self._stop_event.clear()
        self._capture_task = asyncio.create_task(self._capture_loop())
        info(
            "Camera capture started",
            controller_id=self.controller_id,
            device_index=self.device_index,
        )

    async def stop_capture(self) -> None:
        self._stop_event.set()
        if self._capture_task:
            self._capture_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._capture_task
            self._capture_task = None

    async def cleanup_capture(self) -> None:
        if self._capture is not None:
            await run_camera_io(self._capture.release)
            self._capture = None
