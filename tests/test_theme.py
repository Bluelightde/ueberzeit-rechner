"""
Unit-Tests für die Theme-Auflösung (auto/light/dark) in UeberstundenApp.

Getestet wird die reine Entscheidungslogik von `_resolve_dark` über einen
Shim – ohne QApplication, da nur `settings` und `_system_is_dark` gebraucht werden.
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, protected-access
from types import SimpleNamespace
import pytest

pytest.importorskip("PyQt6")
from main import UeberstundenApp  # noqa: E402  pylint: disable=wrong-import-position


def _shim(theme, system_dark):
    settings = {} if theme is None else {"theme": theme}
    ns = SimpleNamespace(settings=settings)
    ns._system_is_dark = lambda: system_dark
    return ns


class TestResolveDark:

    def test_light_ist_immer_hell(self):
        assert UeberstundenApp._resolve_dark(_shim("light", True)) is False

    def test_dark_ist_immer_dunkel(self):
        assert UeberstundenApp._resolve_dark(_shim("dark", False)) is True

    def test_auto_folgt_system_dunkel(self):
        assert UeberstundenApp._resolve_dark(_shim("auto", True)) is True

    def test_auto_folgt_system_hell(self):
        assert UeberstundenApp._resolve_dark(_shim("auto", False)) is False

    def test_fehlender_theme_key_verhaelt_sich_wie_auto(self):
        assert UeberstundenApp._resolve_dark(_shim(None, True)) is True
        assert UeberstundenApp._resolve_dark(_shim(None, False)) is False
