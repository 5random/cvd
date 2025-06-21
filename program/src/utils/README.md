# Utilities Package

This folder collects general purpose helpers used across the project. Modules under `config_service`, `log_service`, and `concurrency` provide configuration management, structured logging, and async/thread execution helpers. `data_utils` contains persistence and compression helpers, while `alert_system_utils` and `container.py` implement email alerts and dependency management services.

Legacy packages `config_utils` and `log_utils` remain as thin wrappers around the new services and emit a `DeprecationWarning` when imported.
