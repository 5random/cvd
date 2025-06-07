import cv2
from typing import Dict, Any
from src.utils.concurrency.thread_pool import run_camera_io
from src.utils.log_utils.log_service import warning

async def apply_uvc_settings(capture: cv2.VideoCapture, settings: Dict[str, Any]) -> None:
    """Apply UVC settings asynchronously using run_camera_io."""
    if not capture or not settings:
        return
    prop_map = {
        'brightness': cv2.CAP_PROP_BRIGHTNESS,
        'hue': cv2.CAP_PROP_HUE,
        'contrast': cv2.CAP_PROP_CONTRAST,
        'saturation': cv2.CAP_PROP_SATURATION,
        'sharpness': cv2.CAP_PROP_SHARPNESS,
        'gamma': cv2.CAP_PROP_GAMMA,
        'gain': cv2.CAP_PROP_GAIN,
        'backlight_comp': cv2.CAP_PROP_BACKLIGHT,
        'exposure': cv2.CAP_PROP_EXPOSURE,
    }
    for name, value in settings.items():
        try:
            if name == 'white_balance_auto':
                await run_camera_io(capture.set, cv2.CAP_PROP_AUTO_WB, 1 if value else 0)
            elif name == 'white_balance':
                await run_camera_io(capture.set, cv2.CAP_PROP_WB_TEMPERATURE, float(value))
            elif name == 'exposure_auto':
                await run_camera_io(capture.set, cv2.CAP_PROP_AUTO_EXPOSURE, 1 if value else 0)
            else:
                prop = prop_map.get(name)
                if prop is not None:
                    await run_camera_io(capture.set, prop, float(value))
        except Exception as exc:
            warning(f"Failed to set UVC property {name}: {exc}")


def rotate_frame(frame, rotation: int):
    """Rotate frame by multiples of 90 degrees."""
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame
