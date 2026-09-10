"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to core.retention_analytics.
"""
import sys
import importlib

_impl = importlib.import_module("core.retention_analytics")
sys.modules[__name__] = _impl
