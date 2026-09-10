"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.games.match_game.
"""
import sys
import importlib

_impl = importlib.import_module("ui.games.match_game")
sys.modules[__name__] = _impl
