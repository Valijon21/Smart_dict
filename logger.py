"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to utils.logger.
"""
import sys
import importlib

_impl = importlib.import_module("utils.logger")
sys.modules[__name__] = _impl
