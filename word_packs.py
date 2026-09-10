"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to core.word_packs.
"""
import sys
import importlib

_impl = importlib.import_module("core.word_packs")
sys.modules[__name__] = _impl
