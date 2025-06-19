from .compression_manager import CompressionManager
from .data_cleaner import clean_file
from .data_saver import DataSaver
from .file_management_service import FileMaintenanceService
from .maintenance import MaintenanceManager

# -*- coding: utf-8 -*-
"""
data_utils
----------

Paket mit Hilfsmodulen für Datenkompression, -bereinigung, -verwaltung,
Indexierung und Hintergrundwartung.
"""

# Kompressions-Management

# Kompressions-Service
from .compression_service import (
    CompressionSettings,
    RotationSettings,
    CompressionError,
    CompressionService,
    get_compression_service,
    set_compression_service,
)

# Datenbereinigung

# Daten-Saving

# Dateisystem-Wartung

# Indexierung
from .indexing import (
    DataCategory,
    FileStatus,
    FileMetadata,
    DataIndex,
    DownloadRequest,
    Indexer,
)

# Höhere Datenverwaltung
from .data_manager import (
    DataManager,
    get_data_manager,
    shutdown_data_manager,
)

# Hintergrund-Wartung

__all__ = [
    # compression_service
    "CompressionSettings",
    "RotationSettings",
    "CompressionError",
    "CompressionService",
    "get_compression_service",
    "set_compression_service",
    # compression_manager
    "CompressionManager",
    # data_cleaner
    "clean_file",
    # data_saver
    "DataSaver",
    # file_management_service
    "FileMaintenanceService",
    # indexing
    "DataCategory",
    "FileStatus",
    "FileMetadata",
    "DataIndex",
    "DownloadRequest",
    "Indexer",
    # data_manager
    "DataManager",
    "get_data_manager",
    "shutdown_data_manager",
    # maintenance
    "MaintenanceManager",
]
