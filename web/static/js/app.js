// Überzeit: Live-Rechnung im Formular, Jetzt-Knöpfe, laufende Uhr, Rückfragen, Service Worker.
// Ohne Bibliothek; alles Rechnen passiert auf dem Server (kern.py), hier wird nur angezeigt.
'use strict';
(function () {
  var csrf = document.body.getAttribute('data-csrf') || '';

  function zweistellig(n) { return (n < 10 ? '0' : '') + n; }
  function jetztHHMM() { var d = new Date(); return zweistellig(d.getHours()) + ':' + zweistellig(d.getMinutes()); }
  function zeit(min, plus) {        // wie kern.format_time: '45m', '1h 5m'
    var v = min < 0 ? '-' : (plus && min > 0 ? '+' : ''), a = Math.abs(min);
    return a < 60 ? v + a + 'm' : v + Math.floor(a / 60) + 'h ' + (a % 60) + 'm';
  }
  function klasse(min) { return min > 0 ? 'plus' : (min < 0 ? 'minus' : 'null'); }
  function text(el, t) { el.textContent = t; return el; }
  // Uhrzeitfelder sind Knöpfe der eigenen Uhr (uhr.js); das Feld selbst ist versteckt. Wer den Wert per Skript setzt,
  // muss die Anzeige des Knopfs mitziehen.
  function uhrKnopf(f) { return f.id ? document.getElementById(f.id + '-knopf') : (f.nextElementSibling && f.nextElementSibling.classList.contains('uhr-feld') ? f.nextElementSibling : null); }
  function zeitSetzen(f, wert) {
    f.value = wert;
    var k = uhrKnopf(f);
    if (k) { k.textContent = wert ? wert.slice(0, 5) : '--:--'; k.classList.toggle('ohne-zeit', !wert); }
  }
  function neu(tag, cls, t) { var e = document.createElement(tag); if (cls) e.className = cls; if (t != null) e.textContent = t; return e; }

  // --- Am Handy: Datum, Uhrzeit und Auswahllisten geben den Fokus nach der Auswahl wieder ab, sonst bliebe ihr Rahmen
  // stehen, bis man woanders hintippt (Wunsch Micha 14.10.2026). Tippfelder behalten ihn, solange die Tastatur offen ist.
  if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) {
    document.addEventListener('change', function (ev) {
      var el = ev.target;
      if (el.matches && el.matches('input[type=date], input[type=time], input[type=checkbox], input[type=radio], select')) el.blur();
    });
  }

  // --- Rückfragen vor dem Absenden (Löschen, Abmelden überall) ---
  // (am Dokument statt je Formular: auch für nachgeladene Formulare, z. B. im Tages-Popup des Kalenders)
  document.addEventListener('submit', function (ev) {
    var f = ev.target;
    if (f.matches && f.matches('form[data-frage]') && !window.confirm(f.getAttribute('data-frage'))) ev.preventDefault();
  });
  // Auswahlfelder, die sofort umschalten (Monat, Jahr)
  document.querySelectorAll('form[data-sofort] select').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });

  // --- Kalender am Rechner: angeklickter Tag als Popover direkt am Tag (Wunsch 20.10.2026) ---
  // Erst lag der Tag daneben (der Monat schrumpfte), dann als Popup in der Mitte; Micha möchte ihn am Tag selbst.
  // Ohne JavaScript oder am Handy bleibt es beim Abschnitt unter dem Monat. Der Tag wird nachgeladen (dieselbe Seite
  // mit ?tag=), sein Abschnitt kommt in einen nicht-modalen <dialog> neben dem Kästchen, mit Pfeil zum Tag. Die
  // Adresse zeigt den Tag, damit Bearbeiten/Löschen (weiter=…) zurück zum offenen Tag führen; beim Schließen fällt
  // ?tag= weg. Schließen: ✕, Esc, Klick daneben.
  var kal = document.querySelector('.kal'), breit = window.matchMedia('(min-width: 900px)');
  if (kal && window.HTMLDialogElement) {
    var pop = document.createElement('dialog'), popAn = null, popNr = 0;   // popNr: nur die letzte Anfrage zählt
    pop.className = 'tag-popover';
    pop.setAttribute('aria-labelledby', 'tag-popover-titel');
    document.body.appendChild(pop);
    var popSetzen = function () {                  // neben das Kästchen: rechts, sonst links; Pfeil zeigt auf den Tag
      if (!popAn || !pop.open) return;
      var z = popAn.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight, abstand = 12, rand = 12;
      var rechts = z.right + abstand + w <= window.innerWidth - rand;
      var x = rechts ? z.right + abstand : Math.max(rand, z.left - abstand - w);
      var y = Math.min(Math.max(rand, z.top + z.height / 2 - 40), Math.max(rand, window.innerHeight - h - rand));
      pop.classList.toggle('links', !rechts);
      pop.style.left = (x + window.scrollX) + 'px';
      pop.style.top = (y + window.scrollY) + 'px';
      pop.style.setProperty('--pfeil', Math.min(Math.max(14, z.top + z.height / 2 - y), h - 14) + 'px');
    };
    var popZeigen = function (abschnitt, zelle) {
      abschnitt.removeAttribute('id');
      var titel = abschnitt.querySelector('h2');
      if (titel) titel.id = 'tag-popover-titel';
      pop.innerHTML = '<button type="button" class="symbolknopf tag-popover-zu" aria-label="Schließen"><i class="bi bi-x-lg"></i></button>';
      pop.appendChild(abschnitt);
      kal.querySelectorAll('a.gewaehlt').forEach(function (x) { x.classList.remove('gewaehlt'); });
      zelle.classList.add('gewaehlt');
      popAn = zelle;
      if (!pop.open) pop.show();
      popSetzen();
    };
    var direkt = document.getElementById('tag'), direktZelle = kal.querySelector('a.gewaehlt');
    if (direkt && direktZelle && breit.matches) { window.scrollTo(0, 0); popZeigen(direkt, direktZelle); }
    kal.addEventListener('click', function (ev) {
      var a = ev.target.closest('a');
      if (!a || !breit.matches || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) return;
      ev.preventDefault();
      if (pop.open && popAn === a) { pop.close(); return; }   // derselbe Tag nochmal: zu
      var nr = ++popNr;
      fetch(a.href, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }).then(function (html) {
        if (nr !== popNr) return;                    // inzwischen ein anderer Tag angeklickt
        var neu = new DOMParser().parseFromString(html, 'text/html').getElementById('tag');
        if (!neu) { location.href = a.href; return; }
        popZeigen(document.importNode(neu, true), a);
        history.replaceState(null, '', a.href.split('#')[0]);
      }).catch(function () { location.href = a.href; });
    });
    pop.addEventListener('click', function (ev) { if (ev.target.closest('.tag-popover-zu')) pop.close(); });
    document.addEventListener('mousedown', function (ev) {          // daneben geklickt (nicht auf einen anderen Tag)
      if (pop.open && !pop.contains(ev.target) && !(ev.target.closest && ev.target.closest('.kal a'))) pop.close();
    });
    document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && pop.open) pop.close(); });
    window.addEventListener('resize', function () { if (!breit.matches && pop.open) pop.close(); else popSetzen(); });
    pop.addEventListener('close', function () {
      kal.querySelectorAll('a.gewaehlt').forEach(function (x) { x.classList.remove('gewaehlt'); });
      popAn = null;
      var u = new URL(location.href);
      u.searchParams.delete('tag'); u.hash = '';
      history.replaceState(null, '', u.pathname + u.search);
    });
  }

  // --- Eintragsformular ---
  document.querySelectorAll('form.eintrag-form').forEach(function (form) {
    var feld = function (n) { return form.querySelector('[name="' + n + '"]'); };
    var vorschau = form.querySelector('.vorschau');
    var endeVonHand = !!form.getAttribute('data-ohne-id');   // beim Bearbeiten das gespeicherte Ende nicht überschreiben
    var auto = form.getAttribute('data-auto') === '1';
    var zaehler = 0, warte = null;

    function art() { var r = form.querySelector('input[name="art"]:checked'); return r ? r.value : 'work'; }
    function sichtbar() {
      var arbeit = art() === 'work', korrektur = arbeit && feld('korrektur').checked;
      form.querySelectorAll('[data-nur]').forEach(function (el) {
        var nur = el.getAttribute('data-nur');
        var an = (nur === 'arbeit' && arbeit) || (nur === 'abwesend' && !arbeit) ||
                 (nur === 'zeiten' && arbeit && !korrektur) || (nur === 'korrektur' && korrektur);
        el.classList.toggle('versteckt', !an);
      });
      var eigen = feld('eigenes_soll').checked;
      feld('soll').disabled = !eigen;
      var sollFeld = form.querySelector('[data-soll]');
      if (sollFeld) sollFeld.classList.toggle('versteckt', !eigen);
    }

    function zeigen(d) {
      vorschau.classList.remove('warnung');
      vorschau.textContent = '';
      if (d.fehler) { vorschau.appendChild(neu('span', 'leise', d.fehler)); return; }
      if (d.ueberschneidung) {
        vorschau.classList.add('warnung');
        vorschau.textContent = '⚠️ Überschneidung mit ' + d.ueberschneidung;
        return;
      }
      if (d.ende_vorschlag && !endeVonHand) zeitSetzen(feld('ende'), d.ende_vorschlag);
      if (auto && d.pause != null) feld('pause').value = d.pause;
      var zeile = neu('div');
      zeile.appendChild(document.createTextNode('Tag-Saldo '));
      zeile.appendChild(neu('span', 'gross zahl ' + klasse(d.tag_saldo), zeit(d.tag_saldo, true)));
      vorschau.appendChild(zeile);
      var info = 'Netto ' + zeit(d.netto) + ' · Soll ' + (d.soll ? zeit(d.soll) : 'frei') + ' · Pause ' + d.pause + ' min';
      vorschau.appendChild(neu('div', 'leise klein', info));
      if (d.mitternacht) vorschau.appendChild(neu('div', 'leise klein', 'Über Mitternacht: zählt komplett zum Starttag.'));
      (d.warnungen || []).forEach(function (w) { vorschau.appendChild(neu('div', 'warnhinweis', '⚠️ ' + w)); });
    }

    function rechnen(endeVorschlagen) {
      if (art() !== 'work' || feld('korrektur').checked || !feld('start').value || !feld('datum').value) return;
      var nr = ++zaehler;
      fetch('/api/vorschau', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF': csrf },
        body: JSON.stringify({
          datum: feld('datum').value, start: feld('start').value,
          ende: endeVorschlagen && !endeVonHand ? '' : feld('ende').value, pause: feld('pause').value,
          soll: feld('eigenes_soll').checked ? feld('soll').value : '', ohne_id: form.getAttribute('data-ohne-id'),
          ende_vorschlagen: endeVorschlagen && !endeVonHand
        })
      }).then(function (a) {
        if (a.status === 401) { window.location.reload(); return null; }
        return a.json();
      }).then(function (d) { if (d && nr === zaehler) zeigen(d); })
        .catch(function () { if (nr === zaehler) zeigen({ fehler: 'Keine Verbindung – Vorschau nicht möglich.' }); });
    }
    function spaeter(endeVorschlagen) { clearTimeout(warte); warte = setTimeout(function () { rechnen(endeVorschlagen); }, 220); }

    form.querySelectorAll('input[name="art"], [name="korrektur"], [name="eigenes_soll"]').forEach(function (el) {
      el.addEventListener('change', function () { sichtbar(); spaeter(true); });
    });
    feld('datum').addEventListener('change', function () {
      var bis = feld('bis');
      if (bis && (!bis.value || bis.value < feld('datum').value)) bis.value = feld('datum').value;
      spaeter(true);
    });
    // 'change' meldet die eigene Uhr, 'input' ein normales Zeitfeld (falls uhr.js fehlt)
    ['input', 'change'].forEach(function (ereignis) {
      feld('start').addEventListener(ereignis, function () { spaeter(true); });
      feld('soll').addEventListener(ereignis, function () { spaeter(true); });
      feld('ende').addEventListener(ereignis, function () { endeVonHand = !!feld('ende').value; spaeter(false); });
    });
    feld('pause').addEventListener('input', function () { spaeter(false); });
    form.querySelectorAll('[data-jetzt]').forEach(function (k) {
      k.addEventListener('click', function () {
        var n = k.getAttribute('data-jetzt');
        zeitSetzen(feld(n), jetztHHMM());
        if (n === 'ende') endeVonHand = true;
        spaeter(n === 'start');
      });
    });
    form.addEventListener('submit', function () { var b = form.querySelector('button[type=submit]'); setTimeout(function () { b.disabled = true; }, 0); });
    sichtbar();
    rechnen(!endeVonHand);
  });

  // --- Laufende Arbeitszeit ---
  var stempel = document.querySelector('[data-beginn]');
  if (stempel) {
    var beginn = parseInt(stempel.getAttribute('data-beginn'), 10), anzeige = stempel.querySelector('[data-laufzeit]');
    var tick = function () {
      var min = Math.max(0, Math.floor((Date.now() - beginn) / 60000));
      text(anzeige, Math.floor(min / 60) + ':' + zweistellig(min % 60));
    };
    tick();
    setInterval(tick, 15000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) tick(); });
  }

  // --- Einstellungen: Regionen passend zum Land ---
  document.querySelectorAll('select[data-regionen]').forEach(function (land) {
    var region = document.getElementById(land.getAttribute('data-regionen'));
    land.addEventListener('change', function () {
      fetch('/api/regionen/' + encodeURIComponent(land.value), { credentials: 'same-origin' })
        .then(function (a) { return a.json(); })
        .then(function (liste) {
          region.textContent = '';
          region.appendChild(neu('option', '', '– ganzes Land –')).value = '';
          liste.forEach(function (r) { region.appendChild(neu('option', '', r[1])).value = r[0]; });
        });
    });
  });

  // --- Als App: Service Worker ---
  if ('serviceWorker' in navigator && document.body.getAttribute('data-csrf')) {
    navigator.serviceWorker.register('/sw.js').catch(function () { /* ohne Offline-Fähigkeit weiter */ });
  }
})();

// Gerätezugang (Anwesenheit): beim Antippen ganz markieren, damit er sich leicht kopieren lässt
document.querySelectorAll('[data-markieren]').forEach(function (f) {
  f.addEventListener('focus', function () { f.select(); });
});
