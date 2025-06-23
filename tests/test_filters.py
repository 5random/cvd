import time
import pytest

from cvd.data_handler.processing.filters.range_validation_filter import RangeValidationFilter
from cvd.data_handler.processing.filters.simple_moving_avg_filter import MovingAverageFilter
from cvd.data_handler.processing.filters.outlier_detection_filter import OutlierDetectionFilter
from cvd.data_handler.interface.sensor_interface import SensorReading, SensorStatus


@pytest.mark.asyncio
async def test_range_validation_error():
    filt = RangeValidationFilter("rv", min_value=0.0, max_value=10.0)
    reading = SensorReading("s1", 20.0, time.time(), SensorStatus.OK)
    result = await filt.process(reading)
    assert result.success
    processed = result.data
    assert processed.status == SensorStatus.ERROR
    assert processed.value is None
    assert "above maximum" in processed.error_message
    assert processed.metadata["filter_applied"] == "range_validation"
    assert processed.metadata["original_value"] == 20.0


@pytest.mark.asyncio
async def test_moving_average_filter():
    filt = MovingAverageFilter("ma", window_size=3)
    values = [1.0, 2.0, 3.0, 4.0]
    outputs = []
    for v in values:
        reading = SensorReading("s1", v, time.time(), SensorStatus.OK)
        res = await filt.process(reading)
        outputs.append(res.data)
    # first two values unchanged
    assert outputs[0].value == 1.0
    assert outputs[0].metadata.get("filter_applied") != "moving_average"
    assert outputs[1].value == 2.0
    assert outputs[1].metadata.get("filter_applied") != "moving_average"
    # third value averaged over [1,2,3]
    assert outputs[2].value == pytest.approx(2.0)
    assert outputs[2].metadata["filter_applied"] == "moving_average"
    # fourth averaged over [2,3,4]
    assert outputs[3].value == pytest.approx(3.0)
    assert outputs[3].metadata["filter_applied"] == "moving_average"


@pytest.mark.asyncio
async def test_outlier_detection_filter_detects_outlier():
    filt = OutlierDetectionFilter("od", threshold_std=1.0, min_samples=3)
    # prime history
    for v in [10.0, 11.0, 9.0]:
        await filt.process(SensorReading("s1", v, time.time(), SensorStatus.OK))
    outlier = SensorReading("s1", 20.0, time.time(), SensorStatus.OK)
    result = await filt.process(outlier)
    assert result.success
    data = result.data
    assert data.status == SensorStatus.ERROR
    assert data.value is None
    assert "Outlier detected" in data.error_message
    assert data.metadata["filter_applied"] == "outlier_detection"
    assert data.metadata["original_value"] == 20.0


@pytest.mark.asyncio
async def test_outlier_detection_zero_std_dev():
    filt = OutlierDetectionFilter("od2", threshold_std=1.0, min_samples=3)
    for _ in range(3):
        await filt.process(SensorReading("s1", 5.0, time.time(), SensorStatus.OK))
    normal = SensorReading("s1", 5.0, time.time(), SensorStatus.OK)
    result = await filt.process(normal)
    assert result.success
    data = result.data
    assert data.status == SensorStatus.OK
    assert data.value == 5.0
    assert data.metadata.get("filter_applied") != "outlier_detection"
