"""
Vocab Master Pro — Backward Compatibility Shim for Daily Quests.
Automatically forwards to core.daily_quests / services.daily_quests_service.
"""
import sys
import importlib

_impl = importlib.import_module("services.daily_quests_service")
sys.modules[__name__] = _impl
