"""Deprecated compatibility wrapper for :mod:`src.utils.config_service`."""

from ..config_service import *  # noqa: F401,F403 re-export
import sys
import warnings

warnings.warn(
    "src.utils.config_utils is deprecated; use src.utils.config_service instead",
    DeprecationWarning,
    stacklevel=2,
)

module = sys.modules[__name__]
sys.modules.setdefault("src.utils.config_utils.config_service", module)
