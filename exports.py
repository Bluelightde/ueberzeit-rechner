"""
Hilfsfunktionen für den Export von Arbeitseinträgen (CSV, Excel, PDF).
"""
import csv
import logging
from PyQt6.QtCore import QDate, QLocale, QSizeF
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from i18n import get_locale, tr
from logic import format_time, fmt_date, fmt_time_hhmm

logger = logging.getLogger(__name__)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    _OPENPYXL = True
except ImportError:
    _OPENPYXL = False


def _get_export_row_data(e):
    """Gibt (datum_str, zeitraum_str) für einen Eintrag zurück."""
    d = fmt_date(e.date) if e.date else ""
    if e.start and e.end:
        pause_str = f" (-{e.pause}m)" if e.pause > 0 else ""
        zeitraum = f"{fmt_time_hhmm(e.start)} – {fmt_time_hhmm(e.end)}{pause_str}"
    else:
        zeitraum = "–"
    return d, zeitraum


def export_csv(parent, entries, title):
    """Exportiert Einträge als CSV-Datei."""
    file_name, _ = QFileDialog.getSaveFileName(
        parent, tr("CSV Export"), "ueberstunden_export.csv", tr("CSV Dateien (*.csv)"))
    if not file_name:
        return
    try:
        with open(file_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                tr("Datum"), tr("Zeitraum"), "Minuten", tr("Dauer"), tr("Anlass")
            ])
            for e in entries:
                d, zeitraum = _get_export_row_data(e)
                writer.writerow(
                    [d, zeitraum, e.minutes, format_time(e.minutes), e.reason]
                )
            total = sum(e.minutes for e in entries)
            writer.writerow([tr("Gesamt"), "", "", format_time(total), ""])
        QMessageBox.information(parent, tr("Erfolg"), tr("CSV erfolgreich exportiert!"))
    except Exception as ex:  # pylint: disable=broad-except
        QMessageBox.critical(parent, tr("Fehler"),
                             tr("Fehler beim CSV-Export:\n{ex}").format(ex=str(ex)))


def export_xlsx(parent, entries, title):
    """Exportiert Einträge als Excel-Datei (xlsx)."""
    if not _OPENPYXL:
        msg = tr("openpyxl ist nicht installiert.\nBitte ausführen: pip install openpyxl")
        QMessageBox.critical(parent, tr("Fehler"), msg)
        return

    file_name, _ = QFileDialog.getSaveFileName(
        parent, tr("Excel Export"), "ueberstunden_export.xlsx", tr("Excel Dateien (*.xlsx)"))
    if not file_name:
        return
    try:
        total_min = sum(e.minutes for e in entries)
        wb = Workbook()
        ws = wb.active
        ws.title = "Überstunden"

        ws.merge_cells("A1:E1")
        ws["A1"] = tr("Überstunden-Nachweis – {title}").format(title=title)
        ws["A1"].font = Font(bold=True, size=13)
        ws["A1"].alignment = Alignment(horizontal="center")

        hdr_fill = PatternFill("solid", fgColor="3b82f6")
        hdr_font = Font(bold=True, color="FFFFFF")
        hdr_align = Alignment(horizontal="center")
        for col, text in enumerate(
            [tr("Datum"), tr("Zeitraum"), "Minuten", tr("Dauer"), tr("Anlass")], 1
        ):
            c = ws.cell(row=3, column=col, value=text)
            c.font = hdr_font
            c.fill = hdr_fill
            c.alignment = hdr_align

        alt_fill = PatternFill("solid", fgColor="f3f4f6")
        for i, e in enumerate(entries):
            r = i + 4
            d, zeitraum = _get_export_row_data(e)
            values = [d, zeitraum, e.minutes, format_time(e.minutes), e.reason]
            for col, val in enumerate(values, 1):
                c = ws.cell(row=r, column=col, value=val)
                if i % 2 == 1:
                    c.fill = alt_fill
            ovt_cell = ws.cell(row=r, column=3)
            if e.minutes > 0:
                ovt_cell.font = Font(color="059669")
            elif e.minutes < 0:
                ovt_cell.font = Font(color="dc2626")

        sum_row = len(entries) + 4
        sum_fill = PatternFill("solid", fgColor="dbeafe")
        ws.merge_cells(f"A{sum_row}:C{sum_row}")
        ws[f"A{sum_row}"] = tr("Gesamtsumme:")
        ws[f"D{sum_row}"] = format_time(total_min)
        for col in range(1, 6):
            c = ws.cell(row=sum_row, column=col)
            c.font = Font(bold=True)
            c.fill = sum_fill

        for col, width in zip("ABCDE", [14, 24, 18, 12, 32]):
            ws.column_dimensions[col].width = width

        wb.save(file_name)
        QMessageBox.information(parent, tr("Erfolg"), tr("Excel-Datei erfolgreich exportiert!"))
    except Exception as ex:  # pylint: disable=broad-except
        QMessageBox.critical(parent, tr("Fehler"),
                             tr("Fehler beim Excel-Export:\n{ex}").format(ex=str(ex)))


def export_pdf(parent, entries, title):
    """Exportiert Einträge als PDF-Datei."""
    file_name, _ = QFileDialog.getSaveFileName(
        parent, tr("PDF Export"), "ueberstunden_export.pdf", tr("PDF Dateien (*.pdf)"))
    if not file_name:
        return
    try:
        total_min = sum(e.minutes for e in entries)
        rows_html = ""
        for i, e in enumerate(entries):
            d, zeitraum = _get_export_row_data(e)
            bg = "#f9fafb" if i % 2 == 1 else "#ffffff"
            col_ov = "#059669" if e.minutes > 0 else ("#dc2626" if e.minutes < 0 else "inherit")
            rows_html += (
                f"<tr style='background:{bg}'>"
                f"<td>{d}</td><td>{zeitraum}</td>"
                f"<td style='color:{col_ov};text-align:right'>"
                f"{format_time(e.minutes, show_plus=True)}</td>"
                f"<td>{e.reason}</td></tr>"
            )

        html = f"""
        <html><head><meta charset="utf-8"><style>
            body {{ font-family: Arial, sans-serif; font-size: 11px; color: #111; }}
            h2 {{ font-size: 14px; margin-bottom: 4px; }}
            p.sub {{ color: #666; font-size: 10px; margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
            th {{ background: #3b82f6; color: #fff; padding: 5px 8px; text-align: left; }}
            td {{ border-bottom: 1px solid #e5e7eb; padding: 4px 8px; }}
            tr.sum td {{ background: #dbeafe; font-weight: bold; }}
        </style></head><body>
        <h2>{tr('Überstunden-Nachweis')}</h2>
        <p class="sub">{title} &nbsp;·&nbsp;
           {tr('Erstellt am {d}').format(
               d=get_locale().toString(QDate.currentDate(), QLocale.FormatType.ShortFormat)
           )}</p>
        <table>
          <tr><th>{tr('Datum')}</th><th>{tr('Zeitraum')}</th>
              <th>{tr('Überstunden')}</th><th>{tr('Anlass')}</th></tr>
          {rows_html}
          <tr class="sum">
            <td colspan="2">{tr('Gesamtsumme:')}</td>
            <td style='text-align:right'>
              {format_time(total_min, show_plus=True)}</td><td></td>
          </tr>
        </table>
        </body></html>"""

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_name)

        doc = QTextDocument()
        doc.setHtml(html)
        doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
        doc.print(printer)

        QMessageBox.information(parent, tr("Erfolg"), tr("PDF erfolgreich exportiert!"))
    except Exception as ex:  # pylint: disable=broad-except
        QMessageBox.critical(parent, tr("Fehler"),
                             tr("Fehler beim PDF-Export:\n{ex}").format(ex=str(ex)))
