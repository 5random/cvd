"""Compatibility layer to allow importing modules via both ``src`` and
``program.src`` prefixes.

This module ensures that importing a submodule using either name yields the same
module object.  It installs a lightweight import hook that mirrors modules under
``src.*`` and ``program.src.*`` on first import.
"""

from __future__ import annotations

import importlib
import sys
from importlib import abc, util


_SRC_PREFIX = "src."
_PROG_PREFIX = "program.src."


def _other_name(name: str) -> str | None:
    """Return the corresponding alias for ``name`` or ``None``."""

    if name.startswith(_SRC_PREFIX):
        return _PROG_PREFIX + name[len(_SRC_PREFIX) :]
    if name.startswith(_PROG_PREFIX):
        return _SRC_PREFIX + name[len(_PROG_PREFIX) :]
    return None


def _alias_existing(name: str) -> None:
    """Ensure both prefixes for ``name`` point to the same module."""

    other = _other_name(name)
    if not other:
        return
    mod = sys.modules.get(name) or sys.modules.get(other)
    if mod is None:
        return
    sys.modules[name] = mod
    sys.modules[other] = mod


class _AliasLoader(abc.Loader):
    """Loader that delegates to the real module and mirrors it under both names."""

    def create_module(self, spec):
        return None  # use default module creation

    def exec_module(self, module):  # pragma: no cover - thin wrapper
        other = _other_name(module.__name__)
        assert other is not None
        # Temporarily remove finder to avoid recursion
        sys.meta_path.remove(_finder)
        try:
            real_mod = importlib.import_module(other)
        finally:
            sys.meta_path.insert(0, _finder)
        sys.modules[module.__name__] = real_mod
        sys.modules[other] = real_mod


class _AliasFinder(abc.MetaPathFinder):
    """Finder that resolves modules for both prefixes."""

    def find_spec(
        self, fullname, path=None, target=None
    ):  # pragma: no cover - thin wrapper
        other = _other_name(fullname)
        if other is None:
            return None
        sys.meta_path.remove(self)
        try:
            if other in sys.modules:
                spec = util.spec_from_loader(fullname, _AliasLoader(), origin="alias")
            else:
                found = util.find_spec(other)
                if found is None:
                    return None
                spec = util.spec_from_loader(
                    fullname, _AliasLoader(), origin=found.origin
                )
        except (ImportError, AttributeError):  # pragma: no cover - indirect errors
            return None
        finally:
            sys.meta_path.insert(0, self)
        return spec


_finder = _AliasFinder()
sys.meta_path.insert(0, _finder)

# Import the real package and register both root names
module = importlib.import_module("program.src")
sys.modules.setdefault("program.src", module)
sys.modules[__name__] = module

# Mirror any modules that may have been imported before this file executed
for existing in list(sys.modules):
    _alias_existing(existing)
