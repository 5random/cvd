"""ROI utility functions for clamping and rotation."""

from cvd.gui.ui_helpers import notify_later

__all__ = ["clamp_roi", "rotate_roi"]


def clamp_roi(roi, width, height):
    """Clamp ROI to be within frame dimensions."""
    if width is None or height is None:
        return roi
    x, y, w, h = roi
    try:
        ix = int(x)
        iy = int(y)
        iw = int(w)
        ih = int(h)
    except ValueError:
        notify_later("Invalid ROI values", type="warning")
        return roi

    x = max(0, min(ix, width - 1))
    y = max(0, min(iy, height - 1))
    w = max(0, iw)
    h = max(0, ih)
    if x + w > width:
        w = max(0, width - x)
    if y + h > height:
        h = max(0, height - y)
    return x, y, w, h


def rotate_roi(roi, old_rot, new_rot, width, height):
    """Rotate ROI from old rotation to new rotation."""

    valid_angles = {0, 90, 180, 270}
    if old_rot not in valid_angles or new_rot not in valid_angles:
        raise ValueError(
            f"Unsupported rotation angles: {old_rot}, {new_rot}."
            " Allowed values are 0, 90, 180 and 270."
        )

    def _rot(r, rot, w, h):
        x, y, rw, rh = r
        if rot == 90:
            return y, w - x - rw, rh, rw
        if rot == 180:
            return w - x - rw, h - y - rh, rw, rh
        if rot == 270:
            return h - y - rh, x, rh, rw
        return x, y, rw, rh

    if old_rot == new_rot:
        return roi

    # Rotate back to 0
    width_old = width if old_rot in {0, 180} else height
    height_old = height if old_rot in {0, 180} else width
    r0 = _rot(roi, (360 - old_rot) % 360, width_old, height_old)

    # Rotate to new
    r1 = _rot(r0, new_rot, width, height)
    return r1
