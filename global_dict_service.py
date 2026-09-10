"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.global_dict_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.global_dict_service")
sys.modules[__name__] = _impl
