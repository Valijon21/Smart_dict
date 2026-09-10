"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.dialogs.word_packs_dialog.
"""
import sys
import importlib

_impl = importlib.import_module("ui.dialogs.word_packs_dialog")
sys.modules[__name__] = _impl
