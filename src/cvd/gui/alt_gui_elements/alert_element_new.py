"""Compatibility shim for :mod:`alert_element`.

This module re-exports all public symbols from :mod:`alert_element` so that
imports of ``alert_element_new`` continue to work.
"""

from .alert_element import *  # noqa: F401,F403
