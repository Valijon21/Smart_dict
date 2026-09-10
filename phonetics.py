"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to core.phonetics.
"""
import sys
import importlib

_impl = importlib.import_module("core.phonetics")
sys.modules[__name__] = _impl
