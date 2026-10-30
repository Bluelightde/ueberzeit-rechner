// Eigener Kalender statt des Datumsfensters des Browsers (Wunsch Micha 30.10.2026: „hier ist kein Styling“ -- Chrome
// zeigt bei <input type="date"> ein graues Systemfenster, das eine Seite nicht gestalten kann; wie bei der Uhr, uhr.js).
// Aussehen in datum.css (Farben aus --uhr-* der App, sonst eigene Vorgaben).
//
//   Datum.waehlen('2026-11-08', {min: '2026-11-01'}, function (wert) { ... })   wert 'JJJJ-MM-TT'; Abbrechen ruft nicht
//   <input type="date">: am Handy (Finger) ein Knopf mit diesem Kalender -- das Feld bleibt versteckt im Formular und
//   schickt denselben Namen und Wert; am Rechner bleibt es zum Eintippen, sein Kalendersymbol öffnet diesen Kalender.
//   Geteilt über ~/bin/gemeinsam.py (wie uhr.js) -- nur zusammen ändern.
//   Setzt ein Skript feld.value, zieht der Knopf mit; disabled/min/max des Feldes gelten weiter.
(function () {
  'use strict';
  var MON = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  var MON_KURZ = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.', 'Nov.', 'Dez.'];
  var WT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'], WT_LANG = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
  var blatt, titel, raster, monat, gewaehlt, grenzen = {}, fertig = null;

  function zwei(n) { return (n < 10 ? '0' : '') + n; }
  function iso(d) { return d.getFullYear() + '-' + zwei(d.getMonth() + 1) + '-' + zwei(d.getDate()); }
  function lesen(text) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text || '');
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function wtag(d) { return (d.getDay() + 6) % 7; }
  function kurz(d) { return WT[wtag(d)] + '., ' + d.getDate() + '. ' + MON_KURZ[d.getMonth()] + ' ' + d.getFullYear(); }

  function bauen() {
    blatt = document.createElement('dialog');
    blatt.className = 'datum-blatt'; blatt.setAttribute('aria-label', 'Datum wählen');
    blatt.innerHTML =
      '<form method="dialog">' +
      '<div class="datum-kopf"><button type="button" class="datum-pfeil" data-schritt="-1" aria-label="Vormonat"><i class="bi bi-chevron-left"></i></button>' +
      '<span class="datum-titel" aria-live="polite"></span>' +
      '<button type="button" class="datum-pfeil" data-schritt="1" aria-label="Nächster Monat"><i class="bi bi-chevron-right"></i></button></div>' +
      '<div class="datum-wt">' + WT.map(function (w) { return '<span>' + w + '</span>'; }).join('') + '</div>' +
      '<div class="datum-raster" role="grid"></div>' +
      '<div class="datum-knoepfe"><button type="button" class="datum-knopf zweit" data-heute>Heute</button>' +
      '<button value="abbrechen" class="datum-knopf zweit" formnovalidate>Abbrechen</button></div></form>';
    document.body.appendChild(blatt);
    titel = blatt.querySelector('.datum-titel');
    raster = blatt.querySelector('.datum-raster');
    blatt.addEventListener('click', function (e) {
      if (e.target === blatt) { blatt.close(); return; }                  // daneben getippt
      var pfeil = e.target.closest('[data-schritt]');
      if (pfeil) { monat = new Date(monat.getFullYear(), monat.getMonth() + +pfeil.getAttribute('data-schritt'), 1); zeichnen(); return; }
      if (e.target.closest('[data-heute]')) { var h = new Date(); monat = new Date(h.getFullYear(), h.getMonth(), 1); zeichnen(true); return; }
      var tag = e.target.closest('[data-tag]');
      if (tag && !tag.disabled) { var f = fertig; fertig = null; blatt.close(); if (f) f(tag.getAttribute('data-tag')); }
    });
    // Pfeiltasten im Raster: Tag vor/zurück, Woche hoch/runter
    raster.addEventListener('keydown', function (e) {
      var schritt = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
      var jetzt = document.activeElement && document.activeElement.getAttribute('data-tag');
      if (!schritt || !jetzt) return;
      e.preventDefault();
      var d = lesen(jetzt); d.setDate(d.getDate() + schritt);
      if (d.getMonth() !== monat.getMonth() || d.getFullYear() !== monat.getFullYear()) { monat = new Date(d.getFullYear(), d.getMonth(), 1); zeichnen(); }
      var ziel = raster.querySelector('[data-tag="' + iso(d) + '"]');
      if (ziel) ziel.focus();
    });
  }

  function zeichnen(heuteFokus) {
    titel.textContent = MON[monat.getMonth()] + ' ' + monat.getFullYear();
    var start = new Date(monat); start.setDate(1 - wtag(start));
    var heute = iso(new Date()), html = '';
    for (var i = 0; i < 42; i++) {                       // immer 6 Wochen, wie die Monatsansicht
      var d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i), t = iso(d);
      var aus = (grenzen.min && t < grenzen.min) || (grenzen.max && t > grenzen.max);
      var klassen = ['datum-tag', d.getMonth() !== monat.getMonth() ? 'fremd' : '', t === heute ? 'heute' : '',
                     t === gewaehlt ? 'gewaehlt' : '', wtag(d) >= 5 ? 'wochenende' : ''].filter(Boolean).join(' ');
      html += '<button type="button" class="' + klassen + '" data-tag="' + t + '"' + (aus ? ' disabled' : '') +
              ' aria-label="' + WT_LANG[wtag(d)] + ', ' + d.getDate() + '. ' + MON[d.getMonth()] + ' ' + d.getFullYear() + '"' +
              (t === gewaehlt ? ' aria-pressed="true"' : '') + ' tabindex="-1">' + d.getDate() + '</button>';
    }
    raster.innerHTML = html;
    var fokus = raster.querySelector(heuteFokus ? '.heute' : '.gewaehlt') || raster.querySelector('.heute:not(.fremd)')
                || raster.querySelector('.datum-tag:not(.fremd):not([disabled])');
    if (fokus) { fokus.tabIndex = 0; if (blatt.open) fokus.focus(); }
  }

  function waehlen(wert, optionen, rueckruf) {
    if (!blatt) bauen();
    optionen = optionen || {};
    grenzen = { min: optionen.min || '', max: optionen.max || '' };
    gewaehlt = lesen(wert) ? wert : '';
    var d = lesen(wert) || lesen(grenzen.min) || new Date();
    monat = new Date(d.getFullYear(), d.getMonth(), 1);
    fertig = rueckruf;
    zeichnen();
    blatt.showModal();
    var f = raster.querySelector('[tabindex="0"]');
    if (f) f.focus();
  }

  // Wert setzen wie ein Mensch: Feld ändern und change/input melden (app.js hört darauf)
  function setzen(feld, wert) {
    feld.value = wert;
    feld.dispatchEvent(new Event('input', { bubbles: true }));
    feld.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function optionenVon(feld) { return { min: feld.getAttribute('min') || '', max: feld.getAttribute('max') || '' }; }

  // Handy: <input type="date"> -> Knopf; das Feld bleibt (versteckt) im Formular
  function ersetzen(feld) {
    var knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = ((feld.className || '') + ' datum-feld').trim();
    function zeigen() {
      var d = lesen(feld.value);
      knopf.textContent = d ? kurz(d) : 'Datum wählen';
      knopf.classList.toggle('ohne-datum', !d);
      knopf.classList.toggle('aus', feld.disabled);
    }
    if (feld.id) {
      knopf.id = feld.id + '-knopf';
      document.querySelectorAll('label[for="' + feld.id + '"]').forEach(function (l) { l.htmlFor = knopf.id; });
    }
    if (feld.getAttribute('aria-label')) knopf.setAttribute('aria-label', feld.getAttribute('aria-label'));
    // Setzt ein Skript feld.value (z. B. das Ende rutscht mit dem Beginn mit), zieht der Knopf mit
    var echt = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    Object.defineProperty(feld, 'value', {
      configurable: true,
      get: function () { return echt.get.call(this); },
      set: function (v) { echt.set.call(this, v); zeigen(); }
    });
    new MutationObserver(zeigen).observe(feld, { attributes: true, attributeFilter: ['disabled'] });
    feld.type = 'hidden';
    feld.parentNode.insertBefore(knopf, feld.nextSibling);
    zeigen();
    // Ausgegraut: der Klick geht erst weiter (app.js wählt z. B. die Zeile „Am“ aus und gibt das Feld frei), dann
    // öffnet sich der Kalender gleich mit -- ein Tipp statt zwei
    knopf.addEventListener('click', function () {
      var oeffnen = function () {
        // nach der Wahl kein Fokus-Rahmen am Knopf (am Handy stört er nur, Wunsch Micha 14.10.2026 in Überzeit)
        if (!feld.disabled) waehlen(feld.value, optionenVon(feld), function (v) { setzen(feld, v); knopf.blur(); });
      };
      if (feld.disabled) setTimeout(oeffnen, 0); else oeffnen();
    });
  }

  // Rechner: Feld bleibt unverändert zum Tippen (keine Hülle -- das Layout der Apps bleibt heil); ein Klick auf sein
  // Kalendersymbol (rechter Rand) öffnet statt des Browserfensters diesen Kalender
  function ergaenzen(feld) {
    feld.classList.add('datum-getippt');
    function amSymbol(e) {
      var r = feld.getBoundingClientRect();
      return e.clientX >= r.right - 40 && e.clientX <= r.right;
    }
    function oeffnen() {
      if (feld.disabled || feld.readOnly) return;
      waehlen(feld.value, optionenVon(feld), function (v) { setzen(feld, v); feld.focus(); });
    }
    feld.addEventListener('mousedown', function (e) { if (amSymbol(e)) e.preventDefault(); });
    feld.addEventListener('click', function (e) { if (amSymbol(e)) { e.preventDefault(); oeffnen(); } });
    // Der Browser öffnet sein Fenster sonst auch per Alt+↓ / F4 -- dann lieber unseres
    feld.addEventListener('keydown', function (e) {
      if ((e.altKey && e.key === 'ArrowDown') || e.key === 'F4') { e.preventDefault(); oeffnen(); }
    });
  }

  var FINGER = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  window.Datum = { waehlen: waehlen };
  function los() { document.querySelectorAll('input[type=date]').forEach(FINGER ? ersetzen : ergaenzen); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', los); else los();
})();
