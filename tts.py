"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.tts_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.tts_service")
sys.modules[__name__] = _impl
