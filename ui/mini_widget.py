"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.components.mini_widget.
"""
import sys
import importlib

_impl = importlib.import_module("ui.components.mini_widget")
sys.modules[__name__] = _impl
