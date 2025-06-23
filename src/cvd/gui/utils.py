import asyncio
from typing import Any, Awaitable, Callable, AsyncIterator, Optional

import cv2
import numpy as np

from cvd.utils.concurrency import run_camera_io
from cvd.utils.log_service import error

DEFAULT_FPS_CAP = 30

async def generate_mjpeg_stream(
    frame_source: Callable[[], Awaitable[Any]],
    *,
    fps_cap: float = DEFAULT_FPS_CAP,
    request: Optional[Any] = None,
    timeout: float = 3.0,
) -> AsyncIterator[bytes]:
    """Yield JPEG encoded frames from ``frame_source`` for MJPEG streaming."""

    last_sent = 0.0
    fps_cap = max(float(fps_cap), 1.0)
    interval = 1 / fps_cap
    no_frame_start: Optional[float] = None
    placeholder_bytes: Optional[bytes] = None
    placeholder_mode = False

    while True:
        if request is not None:
            try:
                if await request.is_disconnected():
                    break
            except asyncio.CancelledError:
                break

        frame = await frame_source()
        now = asyncio.get_running_loop().time()
        if frame is not None:
            no_frame_start = None
            placeholder_mode = False
            if interval <= 0 or now - last_sent >= interval:
                success, buf = await run_camera_io(cv2.imencode, ".jpg", frame)
                if success:
                    jpeg = buf.tobytes()
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                    last_sent = now
        else:
            if no_frame_start is None:
                no_frame_start = now
            if now - no_frame_start >= timeout:
                if not placeholder_mode:
                    error(f"Camera failed to provide frames for {timeout} seconds")
                    placeholder_mode = True
                    if placeholder_bytes is None:
                        placeholder = np.zeros((10, 10, 3), dtype=np.uint8)
                        success, buf = cv2.imencode(".jpg", placeholder)
                        if success:
                            placeholder_bytes = buf.tobytes()
            if placeholder_mode and placeholder_bytes and (
                interval <= 0 or now - last_sent >= interval
            ):
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + placeholder_bytes
                    + b"\r\n"
                )
                last_sent = now
        await asyncio.sleep(max(0.001, interval))

