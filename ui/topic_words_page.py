"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.views.topic_words_view.
"""
import sys
import importlib

_impl = importlib.import_module("ui.views.topic_words_view")
sys.modules[__name__] = _impl
