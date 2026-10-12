// Service Worker: Überzeit startet wie eine App und zeigt ohne Verbindung den zuletzt geladenen Stand. {{ version }}
//
// 🔑 Drei Regeln:
//    * /static/... kommt aus dem Speicher (Dateinamen tragen ?v=<Version>; neue Version = neuer Speicher).
//    * Seiten kommen FRISCH aus dem Netz und werden dabei gemerkt; ohne Netz kommt die gemerkte Fassung.
//      Weiterleitungen (z. B. abgelaufene Anmeldung) werden nie gemerkt.
//    * Alles unter NIE (Anmeldung, Schnittstellen, ...) geht immer direkt ans Netz.
// 🔑 Abmelden schickt "Clear-Site-Data" -- das löscht diesen Speicher samt Service Worker auf dem Gerät.
'use strict';
const VERSION = {{ version | tojson }};
const STATISCH = 'statisch-' + VERSION;
const SEITEN = 'seiten';
const VORAB = {{ vorab | tojson }};
const NIE = {{ nie | tojson }};

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(STATISCH)
    .then((c) => Promise.all(VORAB.map((u) => c.add(u).catch(() => null))))   // einzelne Fehler nicht fatal
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((namen) => Promise.all(namen.filter((n) => n.startsWith('statisch-') && n !== STATISCH).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

function merken(schluessel, antwort) {
  if (antwort && antwort.ok && !antwort.redirected && antwort.type === 'basic') {
    const kopie = antwort.clone();
    caches.open(SEITEN).then((c) => c.put(schluessel, kopie));
  }
  return antwort;
}

function offlineSeite() {
  return new Response(
    // 🔑 Mit Dunkelmodus (27.09.2026): ohne Farben war diese Seite weiß -- und mit ihr die Leiste unten am Handy
    '<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<meta name="color-scheme" content="light dark"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">' +
    '<style>body{font-family:system-ui,sans-serif;padding:2rem;line-height:1.5;margin:0;background:#fff;color:#333}' +
    '@media (prefers-color-scheme: dark){body{background:#000;color:#ddd}a{color:#8fd3c9}}</style>' +
    '<title>Offline</title><body>' +
    '<h1 style="font-size:1.4rem">Keine Verbindung</h1><p>Diese Seite war auf diesem Gerät noch nicht geöffnet und ist ' +
    'deshalb offline nicht da.</p><p><a href="/">Zur Übersicht</a></p></body></html>',
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

self.addEventListener('fetch', (e) => {
  const anfrage = e.request, url = new URL(anfrage.url);
  if (anfrage.method !== 'GET' || url.origin !== self.location.origin) return;
  if (NIE.some((p) => url.pathname === p || url.pathname.startsWith(p.endsWith('/') ? p : p + '/') || url.pathname.startsWith(p + '?'))) return;
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(caches.match(anfrage).then((t) => t || fetch(anfrage).then((a) => {
      if (a.ok) { const k = a.clone(); caches.open(STATISCH).then((c) => c.put(anfrage, k)); }
      return a;
    })));
    return;
  }
  const seite = anfrage.mode === 'navigate' || (anfrage.headers.get('accept') || '').includes('text/html');
  if (!seite) return;
  const schluessel = url.pathname + url.search;
  e.respondWith(fetch(anfrage).then((a) => merken(schluessel, a)).catch(() =>
    caches.open(SEITEN).then((c) => c.match(schluessel)
      .then((t) => t || (url.pathname === '/' ? c.match('/', { ignoreSearch: true }) : null))
      .then((t) => t || offlineSeite()))));
});

// Seiten im Hintergrund vorladen (z. B. alle Notizen aus der Übersicht) -- nur, was noch fehlt oder älter ist
self.addEventListener('message', (e) => {
  const d = e.data || {};
  if (Array.isArray(d.vorladen)) {
    e.waitUntil(caches.open(SEITEN).then(async (c) => {
      for (const u of d.vorladen.slice(0, 300)) {
        try { merken(u, await fetch(u, { credentials: 'same-origin' })); } catch (f) { break; }   // offline: aufhören
      }
    }));
  }
});

