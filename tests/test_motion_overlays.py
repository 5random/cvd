import numpy as np

from src.gui.gui_elements.gui_webcam_stream_element import CameraStreamComponent
from src.controllers.webcam import MotionDetectionResult


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


def test_bbox_overlay_with_roi():
    comp = _create_component()
    comp.show_bounding_boxes = True
    comp.roi_x = 5
    comp.roi_y = 5
    comp._last_scale = 1.0

    frame = np.zeros((5, 5, 3), dtype=np.uint8)
    res = MotionDetectionResult(
        motion_detected=True,
        motion_area=1.0,
        motion_percentage=1.0,
        motion_regions=1,
        motion_center=(6, 6),
        motion_bbox=(6, 6, 2, 2),
        confidence=0.9,
        frame_delta=None,
        motion_mask=None,
        frame=frame,
    )

    out = comp._apply_motion_overlays(frame, res)

    assert out.shape == frame.shape
    assert out.sum() > 0
    assert not np.array_equal(out, frame)
    assert out[1, 1].any()
