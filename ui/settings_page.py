"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.views.settings_view.
"""
import sys
import importlib

_impl = importlib.import_module("ui.views.settings_view")
sys.modules[__name__] = _impl
