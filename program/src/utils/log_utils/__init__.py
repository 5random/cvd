"""Deprecated compatibility wrapper for :mod:`src.utils.log_service`."""

from ..log_service import *  # noqa: F401,F403 re-export
import sys
import warnings

warnings.warn(
    "src.utils.log_utils is deprecated; use src.utils.log_service instead",
    DeprecationWarning,
    stacklevel=2,
)

module = sys.modules[__name__]
sys.modules.setdefault("src.utils.log_utils", module)
sys.modules.setdefault("src.utils.log_utils.log_service", module)
