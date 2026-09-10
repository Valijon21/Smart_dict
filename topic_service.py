"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.topic_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.topic_service")
sys.modules[__name__] = _impl
