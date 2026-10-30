// Gemeinsame Rückfrage der Homelab-Apps (21.10.2026, Wunsch Micha: kein graues Browserfenster „Auf … wird Folgendes
// angezeigt“ mehr, sondern ein Dialog im Design der App). Geteilt über ~/bin/gemeinsam.py -- nur zusammen ändern.
//
//   frage(text, {ja: 'Löschen'}) -> Promise<true|false>
//   frageKopieren(text)          -> zeigt Text zum Markieren, wenn die Zwischenablage fehlt (http im LAN)
//   <button data-bestaetigen="…">, <a data-bestaetigen="…">   fragt beim Klick
//   <form data-bestaetigen="…"> bzw. <form data-frage="…">     fragt beim Absenden
//
// Aussehen: frage.css, Farben aus --frage-* bzw. den Uhr-Farben der App (--uhr-*).
(function () {
  'use strict';
  // Darf mehrfach laufen (weich.js führt die Skripte nach jedem Seitenwechsel neu aus): die Listener des vorigen
  // Laufs gehen über das AbortController weg, der Dialog wird neu gebaut, wenn er nicht mehr im Dokument hängt.
  if (window.__frageAus) window.__frageAus.abort();
  var aus = window.__frageAus = typeof AbortController === 'function' ? new AbortController() : null;
  var mit = function (capture) { return aus ? { capture: capture, signal: aus.signal } : capture; };

  var dlg, textEl, jaKnopf, neinKnopf, feld;

  function bauen() {
    if (dlg && dlg.isConnected) return;
    dlg = document.createElement('dialog');
    dlg.className = 'frage';
    dlg.setAttribute('aria-labelledby', 'frage-text');
    dlg.innerHTML = '<p class="frage-text" id="frage-text"></p>'
      + '<input class="frage-feld" readonly hidden aria-label="Text zum Kopieren">'
      + '<div class="frage-knoepfe"><button type="button" class="frage-nein">Abbrechen</button>'
      + '<button type="button" class="frage-ja">OK</button></div>';
    document.body.appendChild(dlg);
    textEl = dlg.querySelector('.frage-text');
    feld = dlg.querySelector('.frage-feld');
    jaKnopf = dlg.querySelector('.frage-ja');
    neinKnopf = dlg.querySelector('.frage-nein');
    jaKnopf.addEventListener('click', function () { dlg.close('ja'); });
    neinKnopf.addEventListener('click', function () { dlg.close('nein'); });
    // Klick auf den abgedunkelten Rand = Abbrechen (das Ereignis trifft dann den <dialog> selbst)
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close('nein'); });
  }

  function zeigen(text, ja, nein, kopie) {
    bauen();
    textEl.textContent = text;
    jaKnopf.textContent = ja;
    neinKnopf.textContent = nein || '';
    neinKnopf.hidden = !nein;
    feld.hidden = kopie === undefined;
    feld.value = kopie || '';
    dlg.returnValue = '';
    return new Promise(function (fertig) {
      // 🔑 Enter = OK am Dokument (außer auf „Abbrechen“): Der Fokus bleibt sonst oft auf dem Knopf, der gefragt
      //    hat -- Enter löste ihn erneut aus, und die Frage kam wieder (in der Vorratsliste so passiert).
      var taste = function (e) {
        if (e.key !== 'Enter' || e.target === neinKnopf) return;
        e.preventDefault(); e.stopPropagation(); dlg.close('ja');
      };
      document.addEventListener('keydown', taste, true);
      dlg.addEventListener('close', function () {
        document.removeEventListener('keydown', taste, true);
        fertig(dlg.returnValue === 'ja');
      }, { once: true });
      dlg.showModal();                                  // Esc schließt von selbst (returnValue bleibt leer = nein)
      if (kopie !== undefined) { feld.focus(); feld.select(); } else { jaKnopf.focus(); }
    });
  }

  window.frage = function (text, optionen) {
    optionen = optionen || {};
    if (typeof HTMLDialogElement === 'undefined' || !HTMLDialogElement.prototype.showModal) {
      return Promise.resolve(window.confirm(text));     // sehr alte Browser: lieber das Fenster als gar nicht fragen
    }
    return zeigen(text, optionen.ja || 'OK', optionen.nein || 'Abbrechen');
  };

  window.frageKopieren = function (text, hinweis) {
    if (typeof HTMLDialogElement === 'undefined' || !HTMLDialogElement.prototype.showModal) {
      window.prompt(hinweis || 'Zum Kopieren:', text);
      return Promise.resolve(true);
    }
    return zeigen(hinweis || 'Zum Kopieren markiert – mit Strg+C bzw. „Kopieren“ übernehmen:', 'Fertig', '', text);
  };

  // --- Rückfrage an Knöpfen, Links und Formularen ---
  // 🔑 Erst anhalten, nach „OK“ dasselbe noch einmal auslösen. data-gefragt merkt sich kurz, dass schon gefragt
  //    wurde. Ein Knopf wird erneut geklickt (sein name/value geht so mit), ein Formular per requestSubmit.
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-bestaetigen]');
    if (!el || el.tagName === 'FORM') return;
    if (el.dataset.gefragt === '1') { delete el.dataset.gefragt; return; }
    e.preventDefault();
    e.stopPropagation();
    window.frage(el.getAttribute('data-bestaetigen')).then(function (ja) {
      if (!ja) return;
      el.dataset.gefragt = '1';
      el.click();
    });
  }, mit(true));

  document.addEventListener('submit', function (e) {
    var form = e.target, text = form.getAttribute && (form.getAttribute('data-bestaetigen') || form.getAttribute('data-frage'));
    if (!text) return;
    if (form.dataset.gefragt === '1') { delete form.dataset.gefragt; return; }
    e.preventDefault();
    e.stopPropagation();
    var knopf = e.submitter;
    window.frage(text).then(function (ja) {
      if (!ja) return;
      form.dataset.gefragt = '1';
      if (form.requestSubmit) form.requestSubmit(knopf || undefined); else form.submit();
    });
  }, mit(true));
})();
