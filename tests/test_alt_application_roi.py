import pytest
from program.src.gui.alt_application import SimpleGUIApplication


@pytest.mark.parametrize(
    "roi,width,height,expected",
    [
        ((10, 20, 30, 40), 100, 80, (10, 20, 30, 40)),  # already within bounds
        ((-10, -5, 30, 40), 100, 80, (0, 0, 30, 40)),  # negative coordinates
        ((90, 60, 20, 30), 100, 80, (90, 60, 10, 20)),  # width and height clip
        ((10, 70, 30, 20), 100, 80, (10, 70, 30, 10)),  # height clip only
        ((10, 10, -5, -5), 100, 80, (10, 10, 0, 0)),  # negative size
        ((10, 10, 30, 40), None, 80, (10, 10, 30, 40)),  # width None
        ((10, 10, 30, 40), 100, None, (10, 10, 30, 40)),  # height None
        ((10, 10, 30, 40), None, None, (10, 10, 30, 40)),  # both None
    ],
)
def test_clamp_roi(roi, width, height, expected):
    assert SimpleGUIApplication._clamp_roi(roi, width, height) == expected


@pytest.mark.parametrize(
    "roi,old_rot,new_rot,width,height,expected",
    [
        ((10, 20, 30, 40), 0, 90, 100, 80, (20, 60, 40, 30)),
        ((10, 20, 30, 40), 90, 0, 100, 80, (40, 10, 40, 30)),
        ((-5, 10, 20, 30), 270, 180, 100, 80, (60, -5, 30, 20)),
        ((0, 10, 10, 10), -90, 450, 100, 80, (70, 80, 10, 10)),
        ((5, 5, 10, 10), 180, 180, 100, 80, (5, 5, 10, 10)),  # no rotation change
    ],
)
def test_rot_roi(roi, old_rot, new_rot, width, height, expected):
    assert (
        SimpleGUIApplication._rot_roi(roi, old_rot, new_rot, width, height)
        == expected
    )
