from importlib import import_module
import sys

_elements = import_module("src.gui.alt_gui_elements")
sys.modules[__name__ + ".alt_gui_elements"] = _elements
__all__ = ["alt_gui_elements"]
