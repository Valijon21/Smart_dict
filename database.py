"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to core.database.
"""
import sys
import importlib

_impl = importlib.import_module("core.database")
sys.modules[__name__] = _impl
