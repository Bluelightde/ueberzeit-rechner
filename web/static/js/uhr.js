// Eigene Uhr statt <input type="time"> -- dieselbe Datei in Notizen, Vorratsliste und Wohnungssuche (gemeinsam.py),
// Aussehen in uhr.css. Die Uhr, die Android für Uhrzeit-Felder öffnet, ist ein Systemfenster -- auf
// Michas Pixel ragte sie über den Rand ("Festlegen" abgeschnitten), und eine Seite kann sie nicht gestalten.
// Zifferblatt wie bei Android: außen 1-12, innen 13-23 und 00; erst die Stunde (tippen oder ziehen), beim Loslassen
// weiter zur Minute (jede Minute). Oben Stunde/Minute einzeln antippbar, ⌨ zum Tippen, Pfeiltasten am Zifferblatt.
//
//   Uhr.waehlen('14:00', {ohne: true}, function (wert) { ... })   wert 'HH:MM' oder '' (Ohne); Abbrechen ruft nicht
//   <input type="time"> auf jeder Seite wird automatisch zu einem Knopf mit dieser Uhr (Formulare schicken weiter
//   denselben Namen und Wert). Mit data-ohne bietet die Uhr auch "Ohne" an.
//   <input type="datetime-local"> wird zu Datumsfeld + Uhr-Knopf, der Wert "JJJJ-MM-TTTHH:MM" bleibt.
(function () {
  'use strict';
  var uhr, scheibe, uhrStd, uhrMin, ohneKnopf, H = 0, M = 0, teil = 'std', tasten = false, fertig = null, zieht = false;
  var ZIFFERN = [];                                   // [Element, Wert, Teil]

  function zwei(n) { return (n < 10 ? '0' : '') + n; }
  function lage(e, winkel, r) {
    e.style.left = (50 + r * Math.sin(winkel * Math.PI / 180)) + '%';
    e.style.top = (50 - r * Math.cos(winkel * Math.PI / 180)) + '%';
  }

  function bauen() {
    uhr = document.createElement('dialog');
    uhr.className = 'uhr-blatt'; uhr.id = 'uhr-blatt'; uhr.setAttribute('aria-label', 'Uhrzeit wählen');
    uhr.innerHTML =
      '<form method="dialog">' +
      '<div class="uhr-kopf"><button type="button" class="uhr-teil" data-teil="std" aria-label="Stunde">00</button>' +
      '<span aria-hidden="true">:</span><button type="button" class="uhr-teil" data-teil="min" aria-label="Minute">00</button></div>' +
      '<div class="uhr-scheibe" id="uhr-scheibe" tabindex="0" role="slider" aria-label="Zifferblatt">' +
      '<span class="uhr-zeiger"></span><span class="uhr-punkt"></span></div>' +
      '<div class="uhr-tasten" hidden>' +
      '<input id="uhr-std" inputmode="numeric" maxlength="2" pattern="[01]?[0-9]|2[0-3]" required placeholder="hh" aria-label="Stunde" autocomplete="off">' +
      '<span aria-hidden="true">:</span>' +
      '<input id="uhr-min" inputmode="numeric" maxlength="2" pattern="[0-5]?[0-9]" placeholder="mm" aria-label="Minute" autocomplete="off"></div>' +
      '<div class="uhr-knoepfe">' +
      '<button type="button" class="uhr-symbol" id="uhr-tastatur" aria-label="Zahlen tippen" title="Zahlen tippen"><i class="bi bi-keyboard"></i></button>' +
      '<span class="uhr-rechts"><button value="ohne" class="uhr-knopf zweit" formnovalidate>Ohne</button>' +
      '<button value="abbrechen" class="uhr-knopf zweit" formnovalidate>Abbrechen</button>' +
      '<button value="ok" class="uhr-knopf">OK</button></span></div></form>';
    document.body.appendChild(uhr);
    scheibe = uhr.querySelector('.uhr-scheibe');
    uhrStd = uhr.querySelector('#uhr-std'); uhrMin = uhr.querySelector('#uhr-min');
    ohneKnopf = uhr.querySelector('button[value=ohne]');
    function ziffer(text, wert, winkel, r, t, innen) {
      var e = document.createElement('span');
      e.className = 'uhr-ziffer ' + t + (innen ? ' innen' : '');
      e.textContent = text;
      lage(e, winkel, r);
      scheibe.appendChild(e);
      ZIFFERN.push([e, wert, t]);
    }
    for (var i = 0; i < 12; i++) {
      ziffer(String(i || 12), i || 12, i * 30, 40, 'std', false);
      ziffer(i ? String(i + 12) : '00', i ? i + 12 : 0, i * 30, 26, 'std', true);
      ziffer(zwei(i * 5), i * 5, i * 30, 40, 'min', false);
    }

    scheibe.addEventListener('pointerdown', function (e) {
      zieht = true; scheibe.setPointerCapture(e.pointerId); e.preventDefault(); punkt(e, false);
    });
    scheibe.addEventListener('pointermove', function (e) { if (zieht) punkt(e, false); });
    scheibe.addEventListener('pointerup', function (e) { if (zieht) { zieht = false; punkt(e, true); } });
    scheibe.addEventListener('pointercancel', function () { zieht = false; });
    scheibe.addEventListener('keydown', function (e) {
      var schritt = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[e.key];
      if (schritt) {
        e.preventDefault();
        if (teil === 'std') H = (H + schritt + 24) % 24; else M = (M + schritt + 60) % 60;
        zeichnen();
      } else if (e.key === 'Enter' && teil === 'std') { e.preventDefault(); teil = 'min'; zeichnen(); }
    });
    uhr.querySelectorAll('.uhr-teil').forEach(function (t) {
      t.addEventListener('click', function () { teil = t.getAttribute('data-teil'); if (tasten) tastenZeigen(false); else zeichnen(); });
    });
    uhr.querySelector('#uhr-tastatur').addEventListener('click', function () { tastenZeigen(!tasten); });
    uhrStd.addEventListener('input', function () {
      uhrStd.value = uhrStd.value.replace(/\D/g, '');
      if (uhrStd.checkValidity() && uhrStd.value) H = +uhrStd.value;
      if (uhrStd.value.length === 2 || +uhrStd.value > 2) { uhrMin.focus(); uhrMin.select(); }   // "8" kann nur 08 sein
    });
    uhrMin.addEventListener('input', function () {
      uhrMin.value = uhrMin.value.replace(/\D/g, '');
      if (uhrMin.checkValidity()) M = +uhrMin.value || 0;
    });
    [uhrStd, uhrMin].forEach(function (f) { f.addEventListener('focus', function () { f.select(); }); });
    // Tippen neben die Uhr (auf den abgedunkelten Rand) = Abbrechen (Wunsch Micha 07.10.2026). Ein Klick auf den Rand
    // trifft das <dialog> selbst, alles Innere trifft das Formular. Auch der Druck muss dort beginnen -- sonst schlösse
    // ein Ziehen am Zeiger, das außerhalb endet, die Uhr.
    var randDruck = false;
    uhr.addEventListener('pointerdown', function (e) { randDruck = e.target === uhr; });
    uhr.addEventListener('click', function (e) {
      if (e.target === uhr && randDruck) uhr.close('abbrechen');
      randDruck = false;
    });
    uhr.addEventListener('close', function () {
      var f = fertig, w = uhr.returnValue;
      fertig = null; uhr.returnValue = '';
      if (!f) return;
      if (w === 'ok') f(zwei(H) + ':' + zwei(M));
      else if (w === 'ohne') f('');
    });
  }

  function zeichnen() {
    scheibe.setAttribute('data-teil', teil);
    uhr.querySelectorAll('.uhr-teil').forEach(function (t) {
      t.classList.toggle('aktiv', !tasten && t.getAttribute('data-teil') === teil);
      t.textContent = zwei(t.getAttribute('data-teil') === 'std' ? H : M);
    });
    var innen = teil === 'std' && (H === 0 || H > 12);
    var winkel = teil === 'std' ? (H % 12) * 30 : M * 6, r = innen ? 26 : 40;
    scheibe.style.setProperty('--winkel', winkel + 'deg');
    scheibe.style.setProperty('--laenge', r + '%');
    var p = scheibe.querySelector('.uhr-punkt');
    lage(p, winkel, r);
    p.classList.toggle('zwischen', teil === 'min' && M % 5 !== 0);          // Minute ohne eigene Ziffer
    ZIFFERN.forEach(function (z) { z[0].classList.toggle('gewaehlt', z[2] === teil && z[1] === (teil === 'std' ? H : M)); });
    scheibe.setAttribute('aria-valuetext', zwei(H) + ':' + zwei(M));
    if (document.activeElement !== uhrStd) uhrStd.value = zwei(H);
    if (document.activeElement !== uhrMin) uhrMin.value = zwei(M);
  }

  function tastenZeigen(an) {
    tasten = an;
    scheibe.hidden = an; uhr.querySelector('.uhr-tasten').hidden = !an;
    var k = uhr.querySelector('#uhr-tastatur');
    k.innerHTML = an ? '<i class="bi bi-clock"></i>' : '<i class="bi bi-keyboard"></i>';
    k.setAttribute('aria-label', an ? 'Zifferblatt' : 'Zahlen tippen');
    zeichnen();
    if (an) { uhrStd.focus(); uhrStd.select(); } else scheibe.focus();
  }

  function punkt(e, loslassen) {
    var r = scheibe.getBoundingClientRect(), dx = e.clientX - r.left - r.width / 2, dy = e.clientY - r.top - r.height / 2;
    var winkel = (Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360, abstand = Math.sqrt(dx * dx + dy * dy) / (r.width / 2);
    if (teil === 'std') {
      var i = Math.round(winkel / 30) % 12;
      H = abstand < 0.66 ? (i ? i + 12 : 0) : (i || 12);
    } else M = Math.round(winkel / 6) % 60;
    zeichnen();
    if (loslassen && teil === 'std') { teil = 'min'; zeichnen(); }
  }

  function waehlen(wert, opt, rueckruf) {
    if (!uhr) bauen();
    var m = /^(\d{1,2}):(\d{2})/.exec(wert || ''), jetzt = new Date();
    H = m ? +m[1] % 24 : jetzt.getHours(); M = m ? +m[2] % 60 : jetzt.getMinutes();   // wie Android: sonst die aktuelle Zeit
    teil = 'std'; fertig = rueckruf;
    ohneKnopf.hidden = !(opt && opt.ohne);
    uhr.showModal();
    tastenZeigen(false);
  }

  function feldKnopf(vorlage) {
    var knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = ((vorlage.className || '') + ' uhr-feld').trim();       // z. B. form-control behalten
    if (vorlage.getAttribute('style')) knopf.setAttribute('style', vorlage.getAttribute('style'));
    return knopf;
  }

  // <input type="time"> -> Knopf mit der eigenen Uhr; das Feld bleibt (versteckt) im Formular
  function ersetzen(feld) {
    var knopf = feldKnopf(feld), ohne = feld.hasAttribute('data-ohne');
    function zeigen() { knopf.textContent = feld.value ? feld.value.slice(0, 5) : '--:--'; knopf.classList.toggle('ohne-zeit', !feld.value); }
    if (feld.id) {
      knopf.id = feld.id + '-knopf';
      document.querySelectorAll('label[for="' + feld.id + '"]').forEach(function (l) { l.htmlFor = knopf.id; });
    }
    if (feld.getAttribute('aria-label')) knopf.setAttribute('aria-label', feld.getAttribute('aria-label'));
    feld.type = 'hidden';
    feld.parentNode.insertBefore(knopf, feld.nextSibling);
    zeigen();
    knopf.addEventListener('click', function () {
      waehlen(feld.value, { ohne: ohne }, function (v) {
        feld.value = v; zeigen();
        feld.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  // <input type="datetime-local"> -> Datumsfeld + Uhr-Knopf; das Feld bleibt (versteckt) und bekommt "TagTZeit"
  function ersetzenDatumZeit(feld) {
    var teile = (feld.value || '').split('T'), zeit = (teile[1] || '').slice(0, 5);
    var huelle = document.createElement('span'), tag = document.createElement('input'), knopf = feldKnopf(feld);
    huelle.className = 'uhr-datum-zeit';
    tag.type = 'date'; tag.className = feld.className; tag.value = teile[0] || ''; tag.required = feld.required;
    tag.setAttribute('aria-label', 'Datum');
    if (feld.min) tag.min = feld.min.slice(0, 10);
    if (feld.max) tag.max = feld.max.slice(0, 10);
    if (feld.id) {
      tag.id = feld.id + '-tag'; knopf.id = feld.id + '-knopf';
      document.querySelectorAll('label[for="' + feld.id + '"]').forEach(function (l) { l.htmlFor = tag.id; });
    }
    knopf.setAttribute('aria-label', 'Uhrzeit');
    function abgleichen() {
      feld.value = tag.value && zeit ? tag.value + 'T' + zeit : '';
      knopf.textContent = zeit || '--:--'; knopf.classList.toggle('ohne-zeit', !zeit);
      // Ein verstecktes Feld prüft der Browser nicht -- die fehlende Uhrzeit meldet deshalb das Datumsfeld
      tag.setCustomValidity(feld.required && tag.value && !zeit ? 'Bitte auch eine Uhrzeit wählen.' : '');
    }
    feld.type = 'hidden';
    feld.parentNode.insertBefore(huelle, feld);
    huelle.appendChild(tag); huelle.appendChild(knopf); huelle.appendChild(feld);
    abgleichen();
    tag.addEventListener('change', abgleichen);
    tag.addEventListener('input', abgleichen);
    knopf.addEventListener('click', function () {
      waehlen(zeit, { ohne: !feld.required }, function (v) {
        zeit = v; abgleichen();
        feld.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  window.Uhr = { waehlen: waehlen };
  function los() {
    document.querySelectorAll('input[type=time]').forEach(ersetzen);
    document.querySelectorAll('input[type=datetime-local]').forEach(ersetzenDatumZeit);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', los); else los();
})();
