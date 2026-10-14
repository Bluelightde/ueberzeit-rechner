"""Das Einstellungsfenster ist so breit, dass alle Reiter ganz zu sehen sind (auch mit Stylesheet)."""
# pylint: disable=missing-function-docstring
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from dialogs import SettingsDialog  # noqa: E402  pylint: disable=wrong-import-position


def test_alle_reiter_passen():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    alt = app.styleSheet()
    # breite Reiter wie im dunklen/hellen Stylesheet von main.py, eher großzügiger
    app.setStyleSheet("QTabBar::tab { padding: 5px 18px; margin-right: 2px; font-size: 15px; }")
    try:
        dialog = SettingsDialog({}, None)
        dialog.show()
        app.processEvents()
        leiste = dialog.tabs.tabBar()
        rechts = max(leiste.tabRect(i).right() for i in range(leiste.count()))
        assert rechts < leiste.width(), (rechts, leiste.width(), dialog.width())
        dialog.close()
    finally:
        app.setStyleSheet(alt)
