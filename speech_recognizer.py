"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.speech_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.speech_service")
sys.modules[__name__] = _impl
