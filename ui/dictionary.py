"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.views.dictionary_view.
"""
import sys
import importlib

_impl = importlib.import_module("ui.views.dictionary_view")
sys.modules[__name__] = _impl
