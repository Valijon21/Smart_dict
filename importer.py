"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to utils.importer.
"""
import sys
import importlib

_impl = importlib.import_module("utils.importer")
sys.modules[__name__] = _impl
