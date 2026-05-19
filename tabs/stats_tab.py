"""
Eigenständiges Widget für den Diagramm- und Statistik-Tab.

Layout:
 - oben: KPI-Leiste mit den wichtigsten Kennzahlen
 - dann:  Zeitraum-Filter (Letzte 12 Monate / Aktuelles Jahr / Vorjahr / Alle)
 - unten: drei Diagramme — kumulativer Saldo-Verlauf (oben, voll breit),
          Monats-Balkendiagramm (unten links), ⌀ Saldo je Wochentag (unten rechts).
"""
import copy
from collections import defaultdict
from datetime import datetime

import matplotlib.path as _mpath
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


def _path_deepcopy_fixed(self, memo):
    # Workaround: upstream __deepcopy__ omits memo[id(self)] assignment,
    # causing infinite recursion when tick props are copied during canvas.draw().
    cls = self.__class__
    result = cls.__new__(cls)
    memo[id(self)] = result
    for k, v in self.__dict__.items():
        setattr(result, k, copy.deepcopy(v, memo))
    return result


_mpath.Path.__deepcopy__ = _path_deepcopy_fixed

# pylint: disable=wrong-import-position
from PyQt6.QtCore import QDate, QLocale
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from i18n import get_locale, tr
from logic import COLOR_NEGATIVE, COLOR_POSITIVE, format_time


# pylint: disable=too-many-instance-attributes,too-few-public-methods
class StatsTab(QWidget):
    """Statistik-Tab mit KPI-Leiste, Zeitraum-Filter und Diagramm-Übersicht."""

    PERIOD_LAST_12 = "12months"
    PERIOD_YEAR = "year"
    PERIOD_PREVIOUS_YEAR = "previous"
    PERIOD_ALL = "all"

    def __init__(self, settings, parent=None):
        """Initialisiert das Widget und baut KPI-Leiste, Filter und Canvas auf."""
        super().__init__(parent)
        self.settings = settings
        self.entries = []
        self.kpi_value_labels = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._build_kpi_bar())
        layout.addLayout(self._build_filter_toolbar())

        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

    # --- UI-Aufbau ---

    def _build_kpi_bar(self) -> QFrame:
        """Erstellt die horizontale KPI-Leiste."""
        container = QFrame()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)
        kpi_keys = [
            ("total", tr("Gesamt-Saldo")),
            ("avg", tr("⌀ pro Monat")),
            ("best", tr("Bester Monat")),
            ("worst", tr("Schlechtester Monat")),
            ("streak_plus", tr("Längste Plus-Serie")),
            ("streak_minus", tr("Längste Minus-Serie")),
        ]
        for key, title in kpi_keys:
            card, value_label = self._build_kpi_card(title)
            self.kpi_value_labels[key] = value_label
            h_layout.addWidget(card)
        return container

    @staticmethod
    def _build_kpi_card(title: str):
        """Erstellt eine einzelne KPI-Kachel und gibt (Frame, Value-Label) zurück."""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        v_layout = QVBoxLayout(card)
        v_layout.setContentsMargins(10, 6, 10, 8)
        v_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: gray;")
        title_font = QFont()
        title_font.setPointSize(9)
        lbl_title.setFont(title_font)
        v_layout.addWidget(lbl_title)

        lbl_value = QLabel("–")
        value_font = QFont()
        value_font.setPointSize(13)
        value_font.setBold(True)
        lbl_value.setFont(value_font)
        v_layout.addWidget(lbl_value)

        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return card, lbl_value

    def _build_filter_toolbar(self) -> QHBoxLayout:
        """Erstellt die Toolbar mit Zeitraum-Filter."""
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(tr("Zeitraum:")))
        self.period_combo = QComboBox()
        self.period_combo.addItem(tr("Letzte 12 Monate"), self.PERIOD_LAST_12)
        self.period_combo.addItem(tr("Aktuelles Jahr"), self.PERIOD_YEAR)
        self.period_combo.addItem(tr("Vorheriges Jahr"), self.PERIOD_PREVIOUS_YEAR)
        self.period_combo.addItem(tr("Alle"), self.PERIOD_ALL)
        self.period_combo.currentIndexChanged.connect(self._update_view)
        toolbar.addWidget(self.period_combo)
        toolbar.addStretch()
        return toolbar

    # --- Daten-Aktualisierung ---

    def refresh(self, entries):
        """Übernimmt eine neue Einträge-Liste und aktualisiert KPIs + Charts."""
        self.entries = entries
        self._update_view()

    def _apply_filter(self, entries):
        """Filtert Einträge gemäß aktuellem Zeitraum-Combo."""
        period = self.period_combo.currentData()
        today = QDate.currentDate()
        if period == self.PERIOD_LAST_12:
            cutoff = today.addMonths(-12).toString("yyyy-MM-dd")
            return [e for e in entries if e.date >= cutoff]
        if period == self.PERIOD_YEAR:
            prefix = f"{today.year():04d}"
            return [e for e in entries if e.date.startswith(prefix)]
        if period == self.PERIOD_PREVIOUS_YEAR:
            prefix = f"{today.year() - 1:04d}"
            return [e for e in entries if e.date.startswith(prefix)]
        return list(entries)

    def _update_view(self):
        """Aktualisiert KPI-Leiste und alle Diagramme."""
        filtered = self._apply_filter(self.entries)
        self._update_kpis(filtered, self.entries)
        self._update_charts(filtered, self.entries)

    # --- KPI-Berechnung ---

    @staticmethod
    def _aggregate(entries):
        """Liefert ``(daily_minutes_dict, monthly_minutes_dict)`` für eine Liste."""
        daily = defaultdict(int)
        monthly = defaultdict(int)
        for e in entries:
            if not e.date:
                continue
            daily[e.date] += e.minutes
            if len(e.date) >= 7:
                monthly[e.date[:7]] += e.minutes
        return daily, monthly

    @staticmethod
    def _longest_streaks(daily: dict):
        """Berechnet die längste Plus- und Minus-Serie (in Tagen)."""
        plus_max = minus_max = plus_cur = minus_cur = 0
        for date_str in sorted(daily.keys()):
            value = daily[date_str]
            if value > 0:
                plus_cur += 1
                minus_cur = 0
                plus_max = max(plus_max, plus_cur)
            elif value < 0:
                minus_cur += 1
                plus_cur = 0
                minus_max = max(minus_max, minus_cur)
            else:
                plus_cur = minus_cur = 0
        return plus_max, minus_max

    def _update_kpis(self, entries, all_entries):
        """Berechnet und setzt alle KPI-Werte.

        ``Gesamt-Saldo`` wird stets über sämtliche Einträge gebildet (analog
        zum Haupt-Tab) — der Zeitraum-Filter wirkt nur auf die übrigen KPIs
        und die Diagramme.
        """
        daily, monthly = self._aggregate(entries)
        total_all = sum(e.minutes for e in all_entries)
        period_sum = sum(monthly.values())
        avg = (period_sum / len(monthly)) if monthly else 0

        best = max(monthly.items(), key=lambda kv: kv[1], default=None)
        worst = min(monthly.items(), key=lambda kv: kv[1], default=None)
        plus_streak, minus_streak = self._longest_streaks(daily)

        self._set_kpi("total", format_time(int(total_all), show_plus=True), int(total_all))
        self._set_kpi("avg", format_time(int(avg), show_plus=True), int(avg))
        if best is not None:
            self._set_kpi(
                "best",
                f"{format_time(best[1], show_plus=True)}\n{self._month_label(best[0])}",
                best[1],
            )
        else:
            self._set_kpi("best", "–", 0)
        if worst is not None:
            self._set_kpi(
                "worst",
                f"{format_time(worst[1], show_plus=True)}\n{self._month_label(worst[0])}",
                worst[1],
            )
        else:
            self._set_kpi("worst", "–", 0)
        self._set_kpi("streak_plus", tr("{n} Tage").format(n=plus_streak), 0)
        self._set_kpi("streak_minus", tr("{n} Tage").format(n=minus_streak), 0)

    def _set_kpi(self, key: str, text: str, value_for_color: int):
        """Setzt Text und Farbe einer KPI-Kachel anhand des Vorzeichens."""
        label = self.kpi_value_labels.get(key)
        if label is None:
            return
        label.setText(text)
        if value_for_color > 0:
            label.setStyleSheet(f"color: {COLOR_POSITIVE};")
        elif value_for_color < 0:
            label.setStyleSheet(f"color: {COLOR_NEGATIVE};")
        else:
            label.setStyleSheet("")

    @staticmethod
    def _month_label(month_str: str) -> str:
        """Wandelt 'YYYY-MM' in z.B. 'Mai 2026' (Locale-aware) um."""
        try:
            year, month = month_str.split("-")
            name = get_locale().monthName(int(month), QLocale.FormatType.ShortFormat)
            return f"{name} {year}"
        except (ValueError, AttributeError):
            return month_str

    # --- Diagramme ---

    def _theme_colors(self):
        """Liefert (Hintergrundfarbe, Textfarbe) passend zum aktuellen Theme."""
        is_dark = self.settings.get("dark_mode", False)
        return ('#31363b' if is_dark else '#ffffff',
                '#e0e0e0' if is_dark else '#000000')

    def _update_charts(self, entries, all_entries):
        """Zeichnet die drei Subplots; bei leeren Daten erscheint nur ein Hinweis."""
        self.figure.clear()
        bg_color, text_color = self._theme_colors()
        self.figure.patch.set_facecolor(bg_color)

        if not entries:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)
            ax.text(0.5, 0.5, tr("Keine Daten vorhanden"),
                    color=text_color, ha='center', va='center')
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas.draw()
            return

        gridspec = self.figure.add_gridspec(
            2, 2, height_ratios=[1.4, 1.0], hspace=0.55, wspace=0.30,
            left=0.07, right=0.97, top=0.92, bottom=0.14,
        )
        ax_cum = self.figure.add_subplot(gridspec[0, :])
        ax_month = self.figure.add_subplot(gridspec[1, 0])
        ax_wd = self.figure.add_subplot(gridspec[1, 1])

        for ax in (ax_cum, ax_month, ax_wd):
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color)
            for spine in ax.spines.values():
                spine.set_edgecolor(text_color)
            ax.title.set_color(text_color)
            ax.yaxis.label.set_color(text_color)

        self._draw_cumulative(ax_cum, entries, all_entries, text_color)
        self._draw_monthly(ax_month, entries, text_color)
        self._draw_weekday(ax_wd, entries, text_color)

        self.canvas.draw()

    # pylint: disable=too-many-locals,too-many-branches
    @staticmethod
    def _draw_cumulative(ax, entries, all_entries, text_color):
        """Aktienkurs-Stil: zeigt den Saldo-Stand am Ende jedes Monats.

        Über *alle* Einträge wird je Monat das kumulative Total berechnet
        (Schlusskurs des Monats). Dargestellt wird nur das Fenster des
        Zeitraum-Filters, damit auch ältere Salden korrekt einfließen.
        """
        if not all_entries:
            return

        # 1) Tagessummen über alle Einträge — Reihenfolge nach Datum.
        daily = defaultdict(int)
        undated_minutes = 0
        for e in all_entries:
            if e.date:
                daily[e.date] += e.minutes
            else:
                undated_minutes += e.minutes
        if not daily:
            return

        # 2) Schlusswerte je Monat aufsummieren (durchlaufender cum).
        monthly_close = {}
        cum = 0
        for date_str in sorted(daily.keys()):
            cum += daily[date_str]
            if len(date_str) >= 7:
                monthly_close[date_str[:7]] = cum
        current_total_h = (cum + undated_minutes) / 60

        # 3) Filter-Cutoff (Monatsebene) anwenden.
        filter_dates = [e.date for e in entries if e.date]
        cutoff_month = min(filter_dates)[:7] if filter_dates else min(monthly_close)

        months_in_view = [m for m in sorted(monthly_close) if m >= cutoff_month]
        if not months_in_view:
            return

        xs, ys = [], []
        for month in months_in_view:
            try:
                xs.append(datetime.strptime(f"{month}-01", "%Y-%m-%d"))
            except ValueError:
                continue
            ys.append(monthly_close[month] / 60)
        if not xs:
            return

        # Linien-Segmente einzeln zeichnen: rot wenn min. ein Endpunkt < 0,
        # sonst grün — so wechselt die Farbe an den Nulldurchgängen.
        for i in range(len(xs) - 1):
            seg_color = (COLOR_POSITIVE if ys[i] >= 0 and ys[i + 1] >= 0
                         else COLOR_NEGATIVE)
            ax.plot([xs[i], xs[i + 1]], [ys[i], ys[i + 1]],
                    color=seg_color, linewidth=2.0)
        # Marker pro Punkt einzeln einfärben.
        marker_colors = [COLOR_POSITIVE if y >= 0 else COLOR_NEGATIVE for y in ys]
        ax.scatter(xs, ys, c=marker_colors, s=30, zorder=3,
                   edgecolors='none')
        ax.axhline(0, color=text_color, linewidth=0.7, alpha=0.5, linestyle='--')

        line_color = COLOR_POSITIVE if ys[-1] >= 0 else COLOR_NEGATIVE

        # Y-Achse: zwingend 0 mit einbeziehen, plus etwas Luft.
        y_min, y_max = min(ys + [0]), max(ys + [0])
        padding = max(1.0, (y_max - y_min) * 0.1)
        ax.set_ylim(y_min - padding, y_max + padding)

        # Endwert prominent annotieren — gleichzeitig Sanity-Check für die Daten.
        ax.annotate(
            f"{ys[-1]:+.1f}h",
            xy=(xs[-1], ys[-1]),
            xytext=(8, 0),
            textcoords="offset points",
            color=line_color,
            fontweight='bold',
            fontsize=11,
            va='center',
        )
        ax.set_title(
            tr("Saldo-Verlauf (Monats-Schlussstand) — aktuell {h:+.1f}h").format(
                h=current_total_h
            )
        )
        ax.set_ylabel(tr("Stunden"))

        # Wenn Einträge ohne Datum existieren, klar im Chart kennzeichnen.
        if undated_minutes:
            ax.text(
                0.01, 0.97,
                tr("⚠ {n} Einträge ohne Datum (Summe {h:+.1f}h) "
                   "nicht im Verlauf enthalten").format(
                    n=sum(1 for e in all_entries if not e.date),
                    h=undated_minutes / 60,
                ),
                transform=ax.transAxes,
                color=COLOR_NEGATIVE,
                va='top', ha='left',
                fontsize=9,
                fontweight='bold',
            )

    @staticmethod
    def _draw_monthly(ax, entries, _text_color):
        """Balkendiagramm der Monatssalden."""
        monthly = defaultdict(int)
        for e in entries:
            if e.date and len(e.date) >= 7:
                monthly[e.date[:7]] += e.minutes
        months = sorted(monthly.keys())
        values = [monthly[m] / 60 for m in months]
        colors = [COLOR_POSITIVE if v >= 0 else COLOR_NEGATIVE for v in values]
        ax.bar(months, values, color=colors)
        ax.set_title(tr("Monatlicher Saldo (Stunden)"))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment('right')

    @staticmethod
    def _draw_weekday(ax, entries, _text_color):
        """Balkendiagramm: durchschnittlicher Saldo je Wochentag."""
        daily = defaultdict(int)
        for e in entries:
            if e.date:
                daily[e.date] += e.minutes
        per_wd = defaultdict(list)
        for date_str, total in daily.items():
            try:
                weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()
            except ValueError:
                continue
            per_wd[weekday].append(total)
        labels = [
            get_locale().dayName(i + 1, QLocale.FormatType.ShortFormat) for i in range(7)
        ]
        means = [
            (sum(per_wd[i]) / len(per_wd[i]) / 60) if per_wd[i] else 0 for i in range(7)
        ]
        colors = [COLOR_POSITIVE if m >= 0 else COLOR_NEGATIVE for m in means]
        ax.bar(labels, means, color=colors)
        ax.set_title(tr("⌀ Saldo je Wochentag (h)"))
