"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to services.sound_effects.
"""
import sys
import importlib

_impl = importlib.import_module("services.sound_effects")
sys.modules[__name__] = _impl
