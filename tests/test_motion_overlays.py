import numpy as np

from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from src.controllers.algorithms.motion_detection import MotionDetectionResult


def _create_component():
    return CameraStreamComponent(None)


def _create_result(frame, mask):
    return MotionDetectionResult(
        motion_detected=True,
        motion_area=0.0,
        motion_percentage=0.0,
        motion_regions=0,
        motion_center=None,
        motion_bbox=None,
        confidence=0.0,
        frame_delta=None,
        motion_mask=mask,
        frame=frame,
    )


def test_apply_motion_overlays_grayscale_mask():
    comp = _create_component()
    comp.show_motion_mask = True
    comp.overlay_opacity = 0.5

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:5, 2:5] = 255

    result = comp._apply_motion_overlays(frame, _create_result(frame, mask))

    assert result.shape == frame.shape
    assert result.sum() > 0
    assert not np.array_equal(result, frame)


def test_apply_motion_overlays_color_mask():
    comp = _create_component()
    comp.show_motion_mask = True
    comp.overlay_opacity = 0.5

    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mask = np.zeros((10, 10, 3), dtype=np.uint8)
    mask[2:5, 2:5] = [0, 0, 255]

    result = comp._apply_motion_overlays(frame, _create_result(frame, mask))

    assert result.shape == frame.shape
    assert result.sum() > 0
    assert not np.array_equal(result, frame)
