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
        reader = list(csv.reader(f))

    header = reader[0]
    assert header == ["datetime", "timestamp", "value", "status"]

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
