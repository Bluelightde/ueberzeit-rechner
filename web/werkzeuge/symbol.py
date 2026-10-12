"""Erzeugt die Symbole der Server-Version aus der Geometrie von create_icon.py.

Aufruf (Repo-Wurzel, mit Pillow):  python web/werkzeuge/symbol.py
- static/icons/icon.svg        abgerundet wie das Desktop-Symbol (Browser-Tab, Apple)
- static/icons/maskable.svg    randlos, Uhr in der sicheren Zone (Android schneidet Kreis/Tropfen aus)
- static/icons/icon-192.png, icon-512.png   randlos und ohne Transparenz (Android zeigt Durchsichtiges schwarz)
"""
import math
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', '..'))
from PIL import Image  # noqa: E402
from create_icon import create_icon, LANCZOS  # noqa: E402

ZIEL = os.path.join(HIER, '..', 'static', 'icons')
BLAU, DUNKEL, GOLD = '#2962b2', '#1a3c73', '#ffc107'


def _linie(cx, cy, winkel, r_in, r_aus, farbe, breite):
    a = math.radians(winkel - 90)
    return (f'<line x1="{cx + r_in * math.cos(a):.1f}" y1="{cy + r_in * math.sin(a):.1f}" '
            f'x2="{cx + r_aus * math.cos(a):.1f}" y2="{cy + r_aus * math.sin(a):.1f}" '
            f'stroke="{farbe}" stroke-width="{breite}"/>')


def uhr(s=1024):
    cx = cy = s // 2
    r_aus, r_blatt = int(s * .40), int(s * .36)
    teile = [f'<circle cx="{cx}" cy="{cy}" r="{r_aus}" fill="{DUNKEL}"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r_blatt}" fill="#fff" fill-opacity=".9"/>']
    for h in range(12):
        teile.append(_linie(cx, cy, h * 30, int(r_blatt * (.88 if h % 3 == 0 else .92)), int(r_blatt * .97), DUNKEL,
                            14 if h % 3 == 0 else 7))
    teile += [_linie(cx, cy, 300, 0, int(r_blatt * .54), DUNKEL, 26), _linie(cx, cy, 0, 0, int(r_blatt * .76), DUNKEL, 18),
              _linie(cx, cy, 60, 0, int(r_blatt * .70), GOLD, 18)]
    px, py, pr = int(s * .72), int(s * .28), int(s * .115)
    arm, dick = int(pr * .52), int(pr * .28)
    teile += [f'<circle cx="{px}" cy="{py}" r="{pr}" fill="{GOLD}"/>',
              f'<rect x="{px - dick}" y="{py - arm}" width="{2 * dick}" height="{2 * arm}" fill="{DUNKEL}"/>',
              f'<rect x="{px - arm}" y="{py - dick}" width="{2 * arm}" height="{2 * dick}" fill="{DUNKEL}"/>',
              f'<circle cx="{cx}" cy="{cy}" r="{int(s * .025)}" fill="{DUNKEL}"/>']
    return '\n  '.join(teile)


def svg(randlos):
    s = 1024
    if randlos:   # Uhr auf 84 %: der Plus-Kreis bleibt in der sicheren Zone (Radius 40 %)
        hinter = f'<rect width="{s}" height="{s}" fill="{BLAU}"/>'
        inhalt = f'<g transform="translate({s * .08:.0f} {s * .08:.0f}) scale(.84)">\n  {uhr(s)}\n  </g>'
    else:
        pad, r = int(s * .04), int(s * .18)
        hinter = f'<rect x="{pad}" y="{pad}" width="{s - 2 * pad}" height="{s - 2 * pad}" rx="{r}" fill="{BLAU}"/>'
        inhalt = uhr(s)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" stroke-linecap="butt">\n'
            f'  {hinter}\n  {inhalt}\n</svg>\n')


def png(groesse):
    s = 1024
    grund = Image.new('RGB', (s, s), BLAU)
    bild = create_icon(s)
    # Desktop-Symbol hat 4 % Rand und runde Ecken: Mitte ausschneiden, randlos auf Blau setzen
    klein = bild.resize((int(s * .84), int(s * .84)), LANCZOS)
    grund.paste(klein, (int(s * .08), int(s * .08)), klein)
    return grund.resize((groesse, groesse), LANCZOS)


if __name__ == '__main__':
    os.makedirs(ZIEL, exist_ok=True)
    for name, randlos in (('icon.svg', False), ('maskable.svg', True)):
        with open(os.path.join(ZIEL, name), 'w', encoding='utf-8') as f:
            f.write(svg(randlos))
    for g in (192, 512):
        png(g).save(os.path.join(ZIEL, f'icon-{g}.png'), optimize=True)
    print('Symbole geschrieben nach', os.path.normpath(ZIEL))
