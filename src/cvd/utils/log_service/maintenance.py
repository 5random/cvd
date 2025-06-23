from __future__ import annotations

import gzip
import shutil
from datetime import datetime, timedelta


def rotate_logs(service) -> None:
    """Manually rotate all logs for the given service."""
    for handler in service._handlers.values():
        if hasattr(handler, "doRollover"):
            handler.doRollover()


def cleanup_old_logs(service) -> None:
    """Remove log files older than the retention period."""
    cutoff_date = datetime.now() - timedelta(days=service.retention_days)
    for log_file in service.log_dir.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_date.timestamp():
            try:
                log_file.unlink()
                service.info(f"Cleaned up old log file: {log_file}")
            except Exception as exc:
                service.error(f"Failed to cleanup log file {log_file}: {exc}")


def compress_old_logs(service) -> None:
    """Compress old log files to save space."""
    compressed_exts = {".gz", ".bz2", ".xz", ".zip"}
    for log_file in service.log_dir.glob("*.log.*"):
        if any(log_file.name.endswith(ext) for ext in compressed_exts):
            continue
        try:
            compressed_file = f"{log_file}.gz"
            with open(log_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            log_file.unlink()
            service.info(f"Compressed log file: {log_file} -> {compressed_file}")
        except Exception as exc:
            service.error(f"Failed to compress log file {log_file}: {exc}")
