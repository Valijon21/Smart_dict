"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to utils.reader_data.
"""
import sys
import importlib

_impl = importlib.import_module("utils.reader_data")
sys.modules[__name__] = _impl
