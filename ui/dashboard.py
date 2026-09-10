"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.views.dashboard_view.
"""
import sys
import importlib

_impl = importlib.import_module("ui.views.dashboard_view")
sys.modules[__name__] = _impl
