"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.games.word_fall_game.
"""
import sys
import importlib

_impl = importlib.import_module("ui.games.word_fall_game")
sys.modules[__name__] = _impl
