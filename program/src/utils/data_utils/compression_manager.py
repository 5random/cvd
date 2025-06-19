from __future__ import annotations

from pathlib import Path
from typing import List

from program.src.utils.log_service import debug, error
from src.utils.data_utils.indexing import FileStatus


class CompressionManager:
    """Handle compression queue operations for DataManager."""

    def __init__(self, manager: "DataManager") -> None:
        self._manager = manager

    def process_compression_queue(self) -> None:
        mgr = self._manager
        if not mgr.auto_compression or not mgr._compression_service:
            return
        idx = mgr._index
        if not idx:
            return
        pending_files = [m for m in idx.files.values() if m.status == FileStatus.PENDING_COMPRESSION]
        updated = False
        for metadata in pending_files:
            try:
                if mgr._compression_service and metadata.file_path.exists():
                    metadata.status = FileStatus.COMPRESSED
                    updated = True
                    debug(f"Processed compression for: {metadata.file_path}")
            except Exception as e:
                error(f"Error processing compression for {metadata.file_path}: {e}")
                metadata.status = FileStatus.ERROR
                updated = True
        if updated:
            mgr._index = idx
            mgr.indexer.save_index()

    def mark_for_compression(self, file_paths: List[str]) -> None:
        mgr = self._manager
        idx = mgr._index
        if not idx:
            return
        for file_path in file_paths:
            if file_path in idx.files:
                metadata = idx.files[file_path]
                if metadata.status == FileStatus.ACTIVE:
                    metadata.status = FileStatus.PENDING_COMPRESSION
        self._manager.indexer.save_index()
