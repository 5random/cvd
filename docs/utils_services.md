# Configuration and Logging Services

This repository bundles shared services under the `src.utils` package. The modern `config_service` and `log_service` packages supersede the deprecated `config_utils` and `log_utils` modules. Compatibility shims have been removed, so always import from the new packages.

## `config_service`

Centralises configuration management and schema validation.  It exposes the
following submodules:

- `loader` – functions for loading/saving JSON configs with deep merging.
- `validation` – helpers for JSON schema validation.
- `maintenance` – utilities for reloading or resetting configuration files.

Import the configuration service via:

```python
from src.utils.config_service import ConfigurationService
```

### ID format

All sensor, controller, webcam and algorithm entries use an ID string. The
identifier becomes part of file paths so only alphanumeric characters, dashes,
underscores and dots are allowed. Valid IDs must match the regular expression
``[A-Za-z0-9_.-]+``. Configuration loading fails if any ID contains disallowed
characters.

## `log_service`

Provides structured logging with rotation and audit features.  A companion
`maintenance` submodule offers log rotation, cleanup and compression helpers.

Use it as follows:

```python
from src.utils.log_service import get_log_service
log = get_log_service()
log.info("message")
```

If no :class:`ConfigurationService` has been registered prior to calling
``get_log_service()``, the logger initialises one automatically using the
project's ``config`` directory. This mirrors the default used by
``ApplicationContainer``.

### Migrating imports

Legacy import paths using the old `config_utils` or `log_utils` packages have been removed. Update any code to import directly from `src.utils.config_service` and `src.utils.log_service`.


