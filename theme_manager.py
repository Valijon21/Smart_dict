"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.theme_manager.
"""
import sys
import importlib

_impl = importlib.import_module("ui.theme_manager")
sys.modules[__name__] = _impl
