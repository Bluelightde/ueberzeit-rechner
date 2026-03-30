"""
Generiert icon.png (1024×1024) für den Überstundenrechner.
Anschließend werden icon.ico (Windows) und icon.icns (macOS) erzeugt.
"""
import math
import os
import struct
import sys
import zlib
from PIL import Image, ImageDraw

SIZE = 1024
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2 * radius, y0 + 2 * radius], fill=fill)
    draw.ellipse([x1 - 2 * radius, y0, x1, y0 + 2 * radius], fill=fill)
    draw.ellipse([x0, y1 - 2 * radius, x0 + 2 * radius, y1], fill=fill)
    draw.ellipse([x1 - 2 * radius, y1 - 2 * radius, x1, y1], fill=fill)


def circle(draw, cx, cy, r, fill=None, outline=None, width=1):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 fill=fill, outline=outline, width=width)


def line_at_angle(draw, cx, cy, angle_deg, r_inner, r_outer, fill, width):
    a = math.radians(angle_deg - 90)
    x0 = cx + r_inner * math.cos(a)
    y0 = cy + r_inner * math.sin(a)
    x1 = cx + r_outer * math.cos(a)
    y1 = cy + r_outer * math.sin(a)
    draw.line([(x0, y0), (x1, y1)], fill=fill, width=width)


# ---------------------------------------------------------------------------
# Icon zeichnen
# ---------------------------------------------------------------------------

def create_icon(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size
    pad = int(s * 0.04)

    # --- Hintergrund (abgerundetes Quadrat) ---
    BG      = (41, 98, 178)     # kräftiges Blau
    DARK    = (26, 60, 115)     # dunkleres Blau für Tiefe
    WHITE   = (255, 255, 255)
    ACCENT  = (255, 193, 7)     # Goldgelb für Überstunden-Zeiger

    r_bg = int(s * 0.18)
    rounded_rect(draw, [pad, pad, s - pad, s - pad], r_bg, BG)

    # --- Äußerer Zifferblatt-Ring ---
    cx = s // 2
    cy = s // 2
    R_outer = int(s * 0.40)
    R_face  = int(s * 0.36)
    R_inner = int(s * 0.30)

    circle(draw, cx, cy, R_outer, fill=DARK)
    circle(draw, cx, cy, R_face,  fill=(255, 255, 255, 230))

    # --- Stunden-Striche ---
    for h in range(12):
        angle = h * 30
        r_t_in  = int(R_face * 0.88) if h % 3 == 0 else int(R_face * 0.92)
        r_t_out = int(R_face * 0.97)
        w = 14 if h % 3 == 0 else 7
        line_at_angle(draw, cx, cy, angle, r_t_in, r_t_out, DARK, w)

    # --- Stunden-Zeiger (zeigt auf ~10 Uhr) ---
    R_hour = int(R_face * 0.54)
    line_at_angle(draw, cx, cy, 300, 0, R_hour, DARK, 26)

    # --- Minuten-Zeiger (zeigt auf ~12 Uhr) ---
    R_min = int(R_face * 0.76)
    line_at_angle(draw, cx, cy, 0, 0, R_min, DARK, 18)

    # --- Überstunden-Zeiger (goldgelb, zeigt auf ~2 Uhr = Mehrarbeit) ---
    R_over = int(R_face * 0.70)
    line_at_angle(draw, cx, cy, 60, 0, R_over, ACCENT, 18)

    # --- Plus-Symbol oben rechts (Überstunden-Symbol) ---
    px = int(s * 0.72)
    py = int(s * 0.28)
    pr = int(s * 0.115)
    circle(draw, px, py, pr, fill=ACCENT)

    arm = int(pr * 0.52)
    thick = int(pr * 0.28)
    draw.rectangle([px - thick, py - arm, px + thick, py + arm], fill=DARK)
    draw.rectangle([px - arm, py - thick, px + arm, py + thick], fill=DARK)

    # --- Mittelpunkt ---
    circle(draw, cx, cy, int(s * 0.025), fill=DARK)

    return img


# ---------------------------------------------------------------------------
# ICO erzeugen (Windows)
# ---------------------------------------------------------------------------

def save_ico(img, path):
    sizes = [256, 128, 64, 48, 32, 16]
    images = []
    for sz in sizes:
        images.append(img.resize((sz, sz), Image.LANCZOS))
    images[0].save(path, format="ICO",
                   sizes=[(im.size[0], im.size[1]) for im in images],
                   append_images=images[1:])
    print(f"  Gespeichert: {path}")


# ---------------------------------------------------------------------------
# ICNS erzeugen (macOS) — ohne iconutil, nur mit Pillow + struct/zlib
# ---------------------------------------------------------------------------

def _png_bytes(img, size):
    resized = img.resize((size, size), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


ICNS_TYPES = [
    (32,   b'ic11'),
    (64,   b'ic12'),
    (128,  b'ic07'),
    (256,  b'ic08'),
    (512,  b'ic09'),
    (1024, b'ic10'),
]


def save_icns(img, path):
    chunks = []
    for size, tag in ICNS_TYPES:
        data = _png_bytes(img, size)
        # jeder Chunk: 4 Bytes Tag + 4 Bytes Länge (inkl. Header) + Daten
        chunk_len = 8 + len(data)
        chunks.append(struct.pack('>4sI', tag, chunk_len) + data)

    body = b''.join(chunks)
    # ICNS-Header: magic 'icns' + Gesamtlänge (8 + body)
    header = b'icns' + struct.pack('>I', 8 + len(body))

    with open(path, 'wb') as f:
        f.write(header + body)
    print(f"  Gespeichert: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Erstelle Icon …")
    icon = create_icon(SIZE)

    png_path  = os.path.join(OUT_DIR, 'icon.png')
    ico_path  = os.path.join(OUT_DIR, 'icon.ico')
    icns_path = os.path.join(OUT_DIR, 'icon.icns')

    icon.save(png_path)
    print(f"  Gespeichert: {png_path}")

    save_ico(icon, ico_path)
    save_icns(icon, icns_path)

    print("Fertig.")
