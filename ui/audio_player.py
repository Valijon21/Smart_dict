"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.views.audio_player_view.
"""
import sys
import importlib

_impl = importlib.import_module("ui.views.audio_player_view")
sys.modules[__name__] = _impl
