"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to core.gamification.
"""
import sys
import importlib

_impl = importlib.import_module("core.gamification")
sys.modules[__name__] = _impl
