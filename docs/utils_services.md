# Configuration and Logging Services

This repository bundles shared services under the `src.utils` package.  Two new packages
`config_service` and `log_service` replace the older `config_utils` and
`log_utils` modules.

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

## `log_service`

Provides structured logging with rotation and audit features.  A companion
`maintenance` submodule offers log rotation, cleanup and compression helpers.

Use it as follows:

```python
from src.utils.log_service import get_log_service
log = get_log_service()
log.info("message")
```

### Migrating imports

Legacy paths like `src.utils.config_utils.config_service` and
`src.utils.log_utils.log_service` are still available for backward
compatibility.  New code should import from `src.utils.config_service` and
`src.utils.log_service` instead.

