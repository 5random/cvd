import cv2
from typing import Dict, Any, Optional, Tuple, List
from program.src.utils.concurrency.thread_pool import run_camera_io
from program.src.utils.log_service import warning


async def apply_uvc_settings(
    capture: cv2.VideoCapture,
    settings: Dict[str, Any],
    *,
    controller_id: Optional[str] = None,
) -> None:
    """Apply UVC settings asynchronously using run_camera_io."""
    if not capture or not settings:
        return
    prop_map = {
        "brightness": cv2.CAP_PROP_BRIGHTNESS,
        "hue": cv2.CAP_PROP_HUE,
        "contrast": cv2.CAP_PROP_CONTRAST,
        "saturation": cv2.CAP_PROP_SATURATION,
        "sharpness": cv2.CAP_PROP_SHARPNESS,
        "gamma": cv2.CAP_PROP_GAMMA,
        "gain": cv2.CAP_PROP_GAIN,
        "backlight_compensation": cv2.CAP_PROP_BACKLIGHT,
        "exposure_auto": cv2.CAP_PROP_AUTO_EXPOSURE,
        "exposure": cv2.CAP_PROP_EXPOSURE,
        "white_balance_auto": cv2.CAP_PROP_AUTO_WB,
        "white_balance": cv2.CAP_PROP_WB_TEMPERATURE,
    }
    for name, value in settings.items():
        try:
            if name == "white_balance_auto":
                await run_camera_io(
                    capture.set, cv2.CAP_PROP_AUTO_WB, 1 if value else 0
                )
            elif name == "white_balance":
                await run_camera_io(
                    capture.set, cv2.CAP_PROP_WB_TEMPERATURE, float(value)
                )
            elif name == "exposure_auto":
                await run_camera_io(
                    capture.set, cv2.CAP_PROP_AUTO_EXPOSURE, 1 if value else 0
                )
            else:
                prop = prop_map.get(name)
                if prop is not None:
                    await run_camera_io(capture.set, prop, float(value))
        except Exception as exc:
            warning(
                "Failed to apply settings property",
                controller_id=controller_id,
                property=name,
                error=str(exc),
            )


def rotate_frame(frame, rotation: int):
    """Rotate frame by multiples of 90 degrees."""
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


async def open_capture(
    device_index: int,
    width: int,
    height: int,
    fps: int,
    *,
    capture_backend: Optional[int] = None,
) -> Optional[cv2.VideoCapture]:
    """Open a VideoCapture with given settings using the camera thread pool."""
    try:
        if capture_backend is not None:
            cap = await run_camera_io(cv2.VideoCapture, device_index, capture_backend)
        else:
            cap = await run_camera_io(cv2.VideoCapture, device_index)
        if not cap or not await run_camera_io(cap.isOpened):
            if cap is not None:
                await run_camera_io(cap.release)
            return None
        await run_camera_io(cap.set, cv2.CAP_PROP_FRAME_WIDTH, int(width))
        await run_camera_io(cap.set, cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        await run_camera_io(cap.set, cv2.CAP_PROP_FPS, int(fps))
        return cap
    except Exception:
        return None


async def probe_camera_modes(
    device_index: int = 0,
    *,
    capture_backend: Optional[int] = None,
) -> List[Tuple[int, int, int]]:
    """Probe camera for supported (width, height, fps) combinations."""
    resolutions = [
        (320, 240),
        (352, 288),
        (640, 480),
        (800, 600),
        (1024, 768),
        (1280, 720),
        (1280, 960),
        (1280, 1024),
        (1920, 1080),
    ]
    fps_values = [5, 10, 15, 20, 24, 30]

    modes: List[Tuple[int, int, int]] = []
    for w, h in resolutions:
        for f in fps_values:
            cap = await open_capture(
                device_index,
                w,
                h,
                f,
                capture_backend=capture_backend,
            )
            if cap is None:
                continue
            try:
                ret, _ = await run_camera_io(cap.read)
            except Exception:
                ret = False
            if ret:
                aw = int(await run_camera_io(cap.get, cv2.CAP_PROP_FRAME_WIDTH))
                ah = int(await run_camera_io(cap.get, cv2.CAP_PROP_FRAME_HEIGHT))
                af = int(round(await run_camera_io(cap.get, cv2.CAP_PROP_FPS)))
                mode = (aw, ah, af or f)
                if mode not in modes:
                    modes.append(mode)
            await run_camera_io(cap.release)

    if not modes:
        modes.append((640, 480, 30))
    modes.sort()
    return modes
