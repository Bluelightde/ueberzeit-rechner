// Gemeinsamer Seitenwechsel ohne Neuladen der Homelab-Apps (30.10.2026, Wunsch Micha: „Ich will nirgends einen
// Ladebalken“). Geteilt über ~/bin/gemeinsam.py -- nur zusammen ändern.
//
// Chrome zeigt bei jeder echten Navigation oben einen Ladebalken, in der installierten App lässt er sich nicht
// abschalten. Dieses Skript holt Seiten deshalb selbst (Links schon beim Antippen) und schickt Formulare selbst ab,
// tauscht <body> aus und trägt die Adresse in den Verlauf ein. Zurück/Vor laden die Seite ebenso nach.
//
// Einbinden: als ERSTES Skript im <head> (ohne defer), damit es Listener und Timer der Seite mitbekommt:
//   <script src="…/weich.js?v=…"></script>
// Spielregeln für die Skripte der App:
//   - Skripte im <head> laufen einmal und bleiben (thema.js …). Skripte im <body> laufen nach jedem Wechsel neu.
//     Was sie am Dokument/Fenster anmelden (Listener, Intervalle, Timer, rAF, EventSource, WebSocket), räumt dieses
//     Skript beim Wechsel ab -- sie brauchen kein eigenes Aufräumen. DOMContentLoaded/load kommen nach dem Neulauf.
//   - Body-Skripte dürfen keine Top-Level-const/let/class haben (der zweite Lauf wäre ein Syntaxfehler) -> IIFE.
//   - beforeunload und pagehide werden beim Verlassen nachgestellt (ungespeichert? -> Rückfrage; Stelle merken).
//   - Ereignis „seite-weg“ am document kurz vor dem Austausch, „seite-da“ danach.
//   - Ausnahmen: data-voll an Link, Formular oder einem Vorfahren (z. B. Abmelden, Wechsel zu anderen Diensten),
//     <body data-weich="aus"> für Seiten, die nur echt geladen werden dürfen. Downloads (Content-Disposition:
//     attachment) speichert das Skript selbst.
//   - Umleitungen mit #Anker: fetch verliert den Anker. Der Server hängt ihn bei Anfragen mit „X-Weich: 1“ als
//     ?weich_anker=… an (siehe weich_anker() in app.py); hier wird er wieder zum Anker.
(function () {
  'use strict';
  if (window.__weich || !window.fetch || !window.DOMParser || !history.pushState || !window.FormData
      || !document.currentScript) return;
  window.__weich = true;

  var W = window, D = document, ET = EventTarget.prototype;
  var orig = {
    an: ET.addEventListener, ab: ET.removeEventListener,
    tO: W.setTimeout.bind(W), tI: W.setInterval.bind(W), cI: W.clearInterval.bind(W),
    rAF: W.requestAnimationFrame && W.requestAnimationFrame.bind(W)
  };
  var NONCE = D.currentScript.nonce || '';
  var epoche = 0, neulauf = false, warteDCL = [], warteLoad = [];
  var merkListener = [], merkIntervalle = [], merkQuellen = [];

  // --- Was die Seite anmeldet, gehört der Seite (außer aus <head>-Skripten und data-einmal) ---
  function bleibt() {
    var s = D.currentScript;
    return !!(s && (s.parentNode === D.head || s.hasAttribute('data-einmal')));
  }
  function imBody(ziel) { return ziel instanceof Node && D.body && D.body.contains(ziel); }
  ET.addEventListener = function (typ, fn, opt) {
    if (fn && !bleibt() && !imBody(this)) {
      if (neulauf && typ === 'DOMContentLoaded' && this === D) { warteDCL.push(fn); return; }
      if (neulauf && typ === 'load' && this === W) { warteLoad.push(fn); return; }
      merkListener.push([this, typ, fn, opt]);
    }
    return orig.an.call(this, typ, fn, opt);
  };
  function wache(fn) {             // Rückruf nur, solange die Seite, die ihn bestellt hat, noch da ist
    if (typeof fn !== 'function' || bleibt()) return fn;
    var e = epoche;
    return function () { if (e === epoche) return fn.apply(this, arguments); };
  }
  W.setTimeout = function (fn) { var a = [].slice.call(arguments); a[0] = wache(fn); return orig.tO.apply(null, a); };
  W.setInterval = function (fn) {
    var a = [].slice.call(arguments), seite = !bleibt();
    a[0] = wache(fn);
    var id = orig.tI.apply(null, a);
    if (seite) merkIntervalle.push(id);
    return id;
  };
  if (orig.rAF) W.requestAnimationFrame = function (fn) { return orig.rAF(wache(fn)); };
  ['EventSource', 'WebSocket'].forEach(function (name) {
    var Echt = W[name];
    if (!Echt) return;
    W[name] = class extends Echt {
      constructor(a, b) { super(a, b); if (!bleibt()) merkQuellen.push(this); }
    };
  });
  function abraeumen() {
    epoche++;
    merkListener.forEach(function (l) { orig.ab.call(l[0], l[1], l[2], l[3]); });
    merkIntervalle.forEach(orig.cI);
    merkQuellen.forEach(function (q) { try { q.close(); } catch (e) { /* schon zu */ } });
    merkListener = []; merkIntervalle = []; merkQuellen = [];
  }

  // --- Kleine Rückmeldung statt Ladebalken: was angetippt wurde, wird nach kurzer Zeit blasser ---
  try {
    var css = new CSSStyleSheet();
    css.replaceSync('.weich-wartet{opacity:.55;transition:opacity .2s}html.weich-laedt{cursor:progress}'
      + '::view-transition-group(root){animation-duration:.14s}');
    D.adoptedStyleSheets = D.adoptedStyleSheets.concat([css]);
  } catch (e) { /* ältere Browser: ohne */ }
  var wartet = null, warteUhr = null;
  function warten(el) {
    fertig();
    wartet = el;
    warteUhr = orig.tO(function () {
      D.documentElement.classList.add('weich-laedt');
      if (wartet) wartet.classList.add('weich-wartet');
    }, 180);
  }
  function fertig() {
    clearTimeout(warteUhr);
    D.documentElement.classList.remove('weich-laedt');
    if (wartet) wartet.classList.remove('weich-wartet');
    wartet = null;
  }

  // --- Verlassen nachstellen ---
  function darfGehen() {
    var e = new Event('beforeunload', { cancelable: true });
    W.dispatchEvent(e);
    // beim nachgestellten Ereignis ist returnValue von Haus aus true; returnValue = '' setzt defaultPrevented mit
    if (!e.defaultPrevented) return Promise.resolve(true);
    var text = 'Diese Seite hat ungespeicherte Änderungen. Trotzdem verlassen?';
    return W.frage ? W.frage(text, { ja: 'Verlassen' }) : Promise.resolve(W.confirm(text));
  }
  function verlassen() {
    try { W.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false })); } catch (e) { /* alt */ }
    D.dispatchEvent(new Event('seite-weg'));
  }

  // --- Seite holen ---
  var vorab = {}, nr = 0, aktuell = location.pathname + location.search;
  function vorladen(url) {          // GET schon beim Antippen; kurz merken fürs gleich folgende Loslassen
    if (!vorab[url]) {
      vorab[url] = fetch(url, { credentials: 'same-origin', headers: { 'X-Weich': '1' } });
      vorab[url].catch(function () {});
      orig.tO(function () { delete vorab[url]; }, 4000);
    }
    return vorab[url];
  }
  function holen(url, opt) {
    if (opt) {
      opt.credentials = 'same-origin';
      opt.headers = { 'X-Weich': '1' };
      return fetch(url, opt);
    }
    var p = vorladen(url);
    delete vorab[url];
    return p;
  }

  function dateiname(r) {
    var cd = r.headers.get('content-disposition') || '', m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
    if (m) return decodeURIComponent(m[1]);
    m = /filename="?([^";]+)"?/i.exec(cd);
    return m ? m[1] : 'download';
  }
  function speichern(r) {
    return r.blob().then(function (b) {
      var a = D.createElement('a'), u = URL.createObjectURL(b);
      a.href = u; a.download = dateiname(r);
      D.body.appendChild(a); a.click(); a.remove();
      orig.tO(function () { URL.revokeObjectURL(u); }, 60000);
    });
  }

  // art: 'neu' (Link/Formular), 'zurueck' (popstate); post: Formular mit POST
  function gehen(url, opt, art, ausloeser) {
    var meine = ++nr, post = !!(opt && opt.method === 'POST');
    var teile = url.split('#'), hash = teile.length > 1 ? '#' + teile.slice(1).join('#') : '';
    url = teile[0];
    warten(ausloeser);
    return holen(url, opt).then(function (r) {
      if (meine !== nr) return;
      var typ = r.headers.get('content-type') || '';
      if (!/text\/html/.test(typ)) {
        fertig();
        if (post || /attachment/i.test(r.headers.get('content-disposition') || '')) return speichern(r);
        location.href = url;                     // Bild, PDF … zeigt der Browser selbst
        return;
      }
      if (!r.ok && !post && art !== 'zurueck' && r.status >= 500) { location.href = url; return; }
      return r.text().then(function (html) {
        if (meine !== nr) return;
        fertig();
        zeigen(html, r.url + (hash && r.url.indexOf('#') < 0 ? hash : ''), art, post);
      });
    }).catch(function () {
      fertig();
      if (meine !== nr) return;
      // fremde Umleitung (Anmeldung beim Authentik …) oder Netz weg: echt laden
      if (post) location.reload(); else location.href = url;
    });
  }

  function zeigen(html, url, art, post) {
    var neu = new DOMParser().parseFromString(html, 'text/html');
    if (!neu.body || neu.body.getAttribute('data-weich') === 'aus') { location.href = url; return; }
    // ?weich_anker=x (vom Server, siehe oben) wird wieder zu #x
    var u = new URL(url, location.href), anker = u.searchParams.get('weich_anker');
    if (anker !== null) { u.searchParams.delete('weich_anker'); u.hash = anker; }
    var ziel = u.pathname + u.search + u.hash;
    var gleich = (u.pathname + u.search) === (location.pathname + location.search);

    // Stylesheets der neuen Seite zuerst laden, sonst blitzt sie ungestylt auf
    var hrefs = {}, neueCss = [];
    D.querySelectorAll('head link[rel=stylesheet]').forEach(function (l) { hrefs[l.href] = l; });
    var behalten = {};
    neu.querySelectorAll('head link[rel=stylesheet]').forEach(function (l) {
      var h = new URL(l.getAttribute('href'), u).href;
      behalten[h] = true;
      if (!hrefs[h]) { var n = D.createElement('link'); n.rel = 'stylesheet'; n.href = h; neueCss.push(n); }
    });
    Promise.all(neueCss.map(function (n) {
      return new Promise(function (ok) { n.onload = n.onerror = ok; D.head.appendChild(n); });
    })).then(function () {
      if (art !== 'zurueck') {
        // Stelle der alten Seite für „Zurück“ merken
        history.replaceState(Object.assign({}, history.state, { weichY: W.scrollY }), '');
      }
      verlassen();
      abraeumen();
      var tauschen = function () {
        Object.keys(hrefs).forEach(function (h) { if (!behalten[h]) hrefs[h].remove(); });
        D.title = neu.title;
        var tc = neu.querySelector('meta[name=theme-color]:not([media])'), tcAlt = D.querySelector('meta[name=theme-color]:not([media])');
        if (tc && tcAlt) tcAlt.content = tc.content;
        // Skripte im <head> der neuen Seite, die hier noch fehlen: einmal ausführen
        var srcs = {};
        D.querySelectorAll('head script[src]').forEach(function (s) { srcs[s.src] = true; });
        neu.querySelectorAll('head script[src]').forEach(function (s) {
          var h = new URL(s.getAttribute('src'), u).href;
          if (!srcs[h]) { var n = D.createElement('script'); n.src = h; if (NONCE) n.nonce = NONCE; D.head.appendChild(n); }
        });
        var body = D.importNode(neu.body, true);
        var skripte = [].slice.call(body.querySelectorAll('script'));
        D.documentElement.replaceChild(body, D.body);
        if (art === 'zurueck') { /* Adresse steht schon */ }
        else if (gleich && (post || u.hash === location.hash)) history.replaceState({ weich: 1 }, '', ziel);
        else history.pushState({ weich: 1 }, '', ziel);
        aktuell = location.pathname + location.search;
        if (art === 'zurueck' && history.state && typeof history.state.weichY === 'number') W.scrollTo(0, history.state.weichY);
        else if (u.hash && D.getElementById(decodeURIComponent(u.hash.slice(1)))) D.getElementById(decodeURIComponent(u.hash.slice(1))).scrollIntoView();
        else W.scrollTo(0, 0);
        // Erst zeigen, wenn die Skripte der neuen Seite gelaufen sind (Uhr-Felder, gemerkte Stelle …), sonst
        // blitzt sie kurz ungefertigt auf; höchstens 1,5 s warten
        return Promise.race([neuLaufen(skripte), new Promise(function (ok) { orig.tO(ok, 1500); })]);
      };
      if (D.startViewTransition && !W.matchMedia('(prefers-reduced-motion: reduce)').matches) D.startViewTransition(tauschen);
      else tauschen();   // ohne Übergang ist die Seite ohnehin sofort zu sehen
    });
  }

  // Importierte <script> laufen nicht von selbst: der Reihe nach durch frische ersetzen
  function neuLaufen(skripte) {
    neulauf = true; warteDCL = []; warteLoad = [];
    var offen = 0, fertigGelaufen = false, erledigt, versprechen = new Promise(function (ok) { erledigt = ok; });
    function ende() {
      if (fertigGelaufen || offen > 0) return;
      fertigGelaufen = true;
      neulauf = false;
      var dcl = warteDCL, ld = warteLoad;
      warteDCL = []; warteLoad = [];
      dcl.forEach(function (fn) { merkListener.push([D, 'DOMContentLoaded', fn]); try { fn.call(D, new Event('DOMContentLoaded')); } catch (e) { console.error(e); } });
      ld.forEach(function (fn) { merkListener.push([W, 'load', fn]); try { fn.call(W, new Event('load')); } catch (e) { console.error(e); } });
      try { W.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: false })); } catch (e) { /* alt */ }
      D.dispatchEvent(new Event('seite-da'));
      erledigt();
    }
    skripte.forEach(function (s) {
      var typ = (s.getAttribute('type') || '').trim().toLowerCase();
      if (typ && typ !== 'text/javascript' && typ !== 'module' && typ !== 'application/javascript') return;   // Daten (JSON …)
      if (s.hasAttribute('data-einmal')) return;
      var n = D.createElement('script');
      [].forEach.call(s.attributes, function (a) { if (a.name !== 'nonce') n.setAttribute(a.name, a.value); });
      if (NONCE) n.nonce = NONCE;
      if (s.src) {
        // Module laufen pro Adresse nur einmal: neue Adresse durch einen Anker
        if (typ === 'module') n.src = s.src.split('#')[0] + '#weich' + epoche;
        n.async = false;
        offen++;
        n.onload = n.onerror = function () { offen--; ende(); };
      } else {
        n.textContent = s.textContent;
      }
      s.replaceWith(n);
    });
    ende();
    return versprechen;
  }

  // --- Was läuft weich? ---
  var DATEI = /\.(pdf|ics|vcf|csv|zip|gz|png|jpe?g|gif|webp|avif|svg|ico|json|txt|xml|xlsx?|docx?|odt|ods|mp3|mp4|webm|webmanifest)$/i;
  function aus(el) {
    return el.closest('[data-voll]') || (D.body && D.body.getAttribute('data-weich') === 'aus');
  }
  function weicherLink(ev) {
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || aus(a) || a.target && a.target !== '_self' || a.hasAttribute('download')) return null;
    if (a.origin !== location.origin || /^(mailto|tel|javascript):/i.test(a.getAttribute('href'))) return null;
    if (a.pathname.indexOf('/static/') === 0 || DATEI.test(a.pathname)) return null;
    // nur ein Anker auf derselben Seite: das macht der Browser
    if (a.pathname === location.pathname && a.search === location.search && a.hash) return null;
    return a;
  }

  orig.an.call(D, 'pointerdown', function (ev) {          // schon beim Antippen holen
    if (ev.button) return;
    var a = weicherLink(ev);
    if (a) vorladen(a.href.split('#')[0]);
  }, { passive: true });
  // Am Fenster (nach allen Listenern der Seite am document): wer selbst preventDefault macht, behält die Sache
  orig.an.call(W, 'click', function (ev) {
    if (ev.defaultPrevented || ev.button || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
    var a = weicherLink(ev);
    if (!a) return;
    ev.preventDefault();
    darfGehen().then(function (ja) { if (ja) gehen(a.href, null, 'neu', a); });
  });
  var sendet = null;
  orig.an.call(W, 'submit', function (ev) {
    var form = ev.target, knopf = ev.submitter;
    if (ev.defaultPrevented || !(form instanceof HTMLFormElement) || aus(form)) return;
    if ((knopf && knopf.closest('[data-voll]'))) return;
    var methode = ((knopf && knopf.getAttribute('formmethod')) || form.getAttribute('method') || 'get').toLowerCase();
    var ziel = (knopf && knopf.hasAttribute('formaction')) ? knopf.formAction : form.action;
    var target = (knopf && knopf.getAttribute('formtarget')) || form.getAttribute('target');
    if (methode === 'dialog' || (target && target !== '_self')) return;
    if (new URL(ziel, location.href).origin !== location.origin) return;
    ev.preventDefault();
    if (sendet === form) return;                             // doppelt getippt
    var daten;
    try { daten = new FormData(form, knopf || undefined); } catch (e) {
      daten = new FormData(form);
      if (knopf && knopf.name) daten.append(knopf.name, knopf.value);
    }
    var gehenNach = function () {
      if (methode === 'get') {
        var u = new URL(ziel, location.href);
        u.search = new URLSearchParams(daten).toString();
        return gehen(u.href, null, 'neu', knopf || form);
      }
      var enctype = ((knopf && knopf.getAttribute('formenctype')) || form.enctype || '').toLowerCase();
      var mitDatei = false;
      daten.forEach(function (v) { if (v instanceof File) mitDatei = true; });
      var body = (enctype === 'multipart/form-data' || mitDatei) ? daten : new URLSearchParams(daten);
      sendet = form;
      return gehen(ziel, { method: 'POST', body: body }, 'neu', knopf || form).then(function () { sendet = null; }, function () { sendet = null; });
    };
    darfGehen().then(function (ja) { if (ja) gehenNach(); });
  });
  orig.an.call(W, 'popstate', function () {
    if (location.pathname + location.search === aktuell) return;   // nur der #Anker hat sich geändert
    gehen(location.href, null, 'zurueck', null);
  });
  // Beginnt eine echte Navigation (data-voll, Adresse getippt), gilt nichts Halbfertiges mehr: sonst bricht ein
  // pushState der weich geholten Seite die echte ab
  orig.an.call(W, 'beforeunload', function (ev) { if (ev.isTrusted) { nr++; fertig(); } });
  history.scrollRestoration = 'manual';
  history.replaceState(Object.assign({}, history.state, { weich: 1 }), '');
  // Aus dem Zwischenspeicher zurück (bfcache): nichts zu tun, die Seite ist so, wie sie war
})();
