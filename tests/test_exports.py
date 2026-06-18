"""
Unit-Tests für die PDF-HTML-Erzeugung in exports.py.

Schwerpunkt: Freitextfelder (Anlass, Titel) müssen HTML-escaped werden, damit
Sonderzeichen wie < > & das erzeugte PDF nicht zerstören.
"""
# pylint: disable=missing-function-docstring, missing-class-docstring, protected-access
import pytest

pytest.importorskip("PyQt6")
from exports import _generate_pdf_html  # noqa: E402  pylint: disable=wrong-import-position
from models import WorkEntry  # noqa: E402  pylint: disable=wrong-import-position


def _entry(reason):
    return WorkEntry(
        id=1, date="2024-06-01", start="08:00", end="17:00",
        pause=30, minutes=510, reason=reason, target_minutes=-1,
    )


class TestPdfHtmlEscaping:

    def test_anlass_wird_escaped(self):
        out = _generate_pdf_html([_entry("<b>Plan & Bau</b>")], "Alle Einträge")
        assert "&lt;b&gt;Plan &amp; Bau&lt;/b&gt;" in out
        # Roh-Markup aus dem Freitext darf NICHT unescaped im Output landen.
        assert "<b>Plan & Bau</b>" not in out

    def test_titel_wird_escaped(self):
        out = _generate_pdf_html([], "Monat <script>")
        assert "&lt;script&gt;" in out

    def test_leerer_anlass_kein_fehler(self):
        out = _generate_pdf_html([_entry("")], "Alle Einträge")
        assert "<table>" in out
