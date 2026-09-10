"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.cefr_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.cefr_service")
sys.modules[__name__] = _impl
