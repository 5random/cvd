import csv
from pathlib import Path
from cvd.utils.data_utils import data_cleaner


def test_clean_file(tmp_path: Path):
    raw = tmp_path / "sample.csv"
    raw.write_text(
        (
            "timestamp,value,status\n"
            "1749374721.0,20.0,ok\n"
            "timestamp,value,status\n"
            "1749374718.0,10.0,ok\n"
            "1749374720.0,,error\n"
            "1749374719.0,15.0,ok\n"
        )
    )

    out_path = data_cleaner.clean_file(raw)
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    expected = [
        ["datetime", "timestamp", "value", "status"],
        ["2025-06-08 09:25:18", "1749374718.000000", "10.00", "ok"],
        ["2025-06-08 09:25:19", "1749374719.000000", "15.00", "ok"],
        ["2025-06-08 09:25:20", "1749374720.000000", "NaN", "error"],
        ["2025-06-08 09:25:21", "1749374721.000000", "20.00", "ok"],
    ]


    # rows should be sorted by timestamp
    timestamps = [float(r[1]) for r in reader[1:]]
    assert timestamps == sorted(timestamps)

    # value for missing reading should be marked as NaN
    values = [row[2] for row in reader[1:]]
    assert "NaN" in values


def test_clean_file_handles_invalid_value(tmp_path: Path):
    raw = tmp_path / "bad.csv"
    raw.write_text(
        (
            "timestamp,value,status\n"
            "1749374721.0,20.0,ok\n"
            "1749374722.0,not_a_number,ok\n"
        )
    )

    out_path = data_cleaner.clean_file(raw)
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    # value that cannot be parsed should be output as NaN
    assert reader[2][2] == "NaN"

