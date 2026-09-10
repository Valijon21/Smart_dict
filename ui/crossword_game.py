"""
SmartDict Backward Compatibility Shim.
Automatically forwards this module to ui.games.crossword_game.
"""
import sys
import importlib

_impl = importlib.import_module("ui.games.crossword_game")
sys.modules[__name__] = _impl
