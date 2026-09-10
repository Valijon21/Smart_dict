"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.dialogs.achievements_dialog.
"""
import sys
import importlib

_impl = importlib.import_module("ui.dialogs.achievements_dialog")
sys.modules[__name__] = _impl
