"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.clipboard_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.clipboard_service")
sys.modules[__name__] = _impl
