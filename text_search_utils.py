"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to utils.text_search_utils.
"""
import sys
import importlib

_impl = importlib.import_module("utils.text_search_utils")
sys.modules[__name__] = _impl
