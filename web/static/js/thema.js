// Hell/Dunkel: Einstellung der Person (data-wahl am <html>), bei "auto" wie das Gerät -- live umschaltend.
// Im <head> VOR dem CSS geladen, damit nichts aufblitzt; eigene Datei wegen der Content-Security-Policy.
(function () {
  var h = document.documentElement, wahl = h.getAttribute('data-wahl') || 'auto';
  var m = window.matchMedia('(prefers-color-scheme: dark)');
  var setze = function () {
    var dunkel = wahl === 'dark' || (wahl === 'auto' && m.matches);
    h.setAttribute('data-thema', dunkel ? 'dark' : 'light');
    var farbe = document.querySelector('meta[name="theme-color"]');
    if (farbe) farbe.setAttribute('content', dunkel ? '#0e1116' : '#f6f7f9');
  };
  setze();
  m.addEventListener('change', setze);
  document.addEventListener('DOMContentLoaded', setze);
})();
