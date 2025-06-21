import pytest
from program.src.data_handler.processing.filters.simple_moving_avg_filter import MovingAverageFilter


def test_window_size_validation():
    with pytest.raises(ValueError):
        MovingAverageFilter("f1", window_size=0)
    with pytest.raises(ValueError):
        MovingAverageFilter("f1", window_size=-5)


def test_valid_window_size():
    f = MovingAverageFilter("f2", window_size=1)
    assert f.window_size == 1
