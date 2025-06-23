from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Any
from src.utils.log_service import warning


def _read_rows(path: Path) -> Iterator[Dict[str, str]]:
    """Yield CSV rows skipping duplicated headers."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("timestamp") == "timestamp":
                continue  # skip internal header lines
            yield row


def _normalize_rows(rows: Iterable[Dict[str, str]]) -> Iterator[Dict[str, Any]]:
    """Yield rows with parsed timestamps and numeric values."""
    for row in rows:
        # Parse timestamp, skip row if malformed
        try:
            ts = float(row["timestamp"])
        except (ValueError, KeyError) as e:
            warning(
                f"Skipping row with invalid timestamp '{row.get('timestamp', None)}': {e}"
            )
            continue
        dt = datetime.fromtimestamp(ts)
        value = row.get("value", "")
        value_float = float(value) if value else float("nan")
        yield {
            "timestamp": ts,
            "datetime": dt,
            "value": value_float,
            "status": row.get("status", ""),
        }


def _write_rows(rows: Iterable[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "timestamp", "value", "status"])
        for row in rows:
            dt_str = row["datetime"].strftime("%Y-%m-%d %H:%M:%S")
            ts_str = f"{row['timestamp']:.6f}"
            value = row["value"]
            if value != value:  # NaN check
                value_str = "NaN"
            else:
                value_str = f"{value:.2f}"
            writer.writerow([dt_str, ts_str, value_str, row["status"]])


def clean_file(
    input_path: Path | str, output_path: Optional[Path | str] = None
) -> Path:
    """Clean a sensor CSV file and write the result."""
    input_path = Path(input_path)
    output_path = (
        Path(output_path)
        if output_path
        else input_path.with_name(f"{input_path.stem}_cleaned.csv")
    )
    rows = sorted(_normalize_rows(_read_rows(input_path)), key=lambda r: r["timestamp"])
    _write_rows(rows, output_path)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean sensor CSV data")
    parser.add_argument("input", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output file path")

    args = parser.parse_args()
    clean_file(args.input, args.output)
