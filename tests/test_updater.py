"""
Tests für updater.py — Selbst-Aktualisierung über GitHub-Releases (ohne Netz: urlopen wird ersetzt).
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,consider-using-with
import hashlib
import io
import json
import os
import tarfile
import zipfile

import pytest

import netz
import updater

ASSETS = [  # so heißen die Pakete von v1.8.0 auf GitHub
    {"name": "Uberzeit-Rechner-1.8.0-linux-x86_64.tar.gz"},
    {"name": "Uberzeit-Rechner-1.8.0-macos-arm64.dmg"},
    {"name": "Uberzeit-Rechner-1.8.0-windows-AMD64.zip"},
]


def test_versionen():
    assert updater.version_tupel("v1.10.2") == (1, 10, 2)
    assert updater.version_tupel("1.9.0-rc1") == (1, 9, 0)
    assert not updater.version_tupel("kaputt")
    assert updater.ist_neuer("v1.9.0", "1.8.1")
    assert updater.ist_neuer("v1.10.0", "1.9.9")          # nicht als Text vergleichen
    assert not updater.ist_neuer("v1.8.0", "1.8.1")
    assert not updater.ist_neuer("v1.8", "1.8.0")
    assert updater.ist_neuer("v1.8.0.1", "1.8")
    assert not updater.ist_neuer("", "1.0.0")


def test_paket_waehlen():
    assert updater.paket_waehlen(ASSETS, "windows", "amd64")["name"].endswith("windows-AMD64.zip")
    assert updater.paket_waehlen(ASSETS, "linux", "x86_64")["name"].endswith(".tar.gz")
    assert updater.paket_waehlen(ASSETS, "macos", "arm64")["name"].endswith(".dmg")
    assert updater.paket_waehlen(ASSETS, "macos", "x86_64") is None
    assert updater.paket_waehlen(ASSETS, "linux", "aarch64") is None


class _Antwort(io.BytesIO):
    def __init__(self, daten):
        super().__init__(daten)
        self.headers = {"Content-Length": str(len(daten))}


@pytest.fixture
def github(monkeypatch):
    """Ersetzt urlopen: Adresse -> Bytes."""
    seiten = {}

    def urlopen(anfrage, timeout=None, context=None):  # pylint: disable=unused-argument
        url = anfrage.full_url
        if url not in seiten:
            raise updater.urllib.error.URLError("nicht erreichbar")
        return _Antwort(seiten[url])

    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    return seiten


def _release(tag, daten=b"paket", digest=True, **mehr):
    return json.dumps({
        "tag_name": tag, "html_url": f"https://github.com/x/releases/tag/{tag}",
        "body": "Neu: Updates",
        "assets": [{"name": f"Uberzeit-Rechner-{tag[1:]}-linux-x86_64.tar.gz", "size": len(daten),
                    "browser_download_url": "https://example.invalid/paket.tar.gz",
                    "digest": "sha256:" + hashlib.sha256(daten).hexdigest() if digest else None}],
        **mehr,
    }).encode()


def test_suchen(github):
    github[updater.API_URL] = _release("v1.9.0")
    info = updater.suchen("1.8.1", system="linux", arch="x86_64")
    assert info["version"] == "1.9.0" and info["notizen"] == "Neu: Updates"
    assert info["paket"]["sha256"] == hashlib.sha256(b"paket").hexdigest()
    assert updater.suchen("1.9.0", system="linux", arch="x86_64") is None
    assert updater.suchen("1.8.1", system="windows", arch="amd64")["paket"] is None   # nur Hinweis
    github[updater.API_URL] = _release("v2.0.0", prerelease=True)
    assert updater.suchen("1.8.1", system="linux", arch="x86_64") is None
    del github[updater.API_URL]
    with pytest.raises(updater.UpdateFehler, match="Keine Verbindung"):
        updater.suchen("1.8.1")


def test_herunterladen(github, tmp_path):
    github[updater.API_URL] = _release("v1.9.0", b"echtes paket")
    github["https://example.invalid/paket.tar.gz"] = b"echtes paket"
    paket = updater.suchen("1.8.1", system="linux", arch="x86_64")["paket"]
    stand = []
    pfad = updater.herunterladen(paket, str(tmp_path), lambda g, t: stand.append((g, t)))
    assert open(pfad, "rb").read() == b"echtes paket" and stand[-1] == (12, 12)
    del github["https://example.invalid/paket.tar.gz"]
    # liegt schon da: nicht neu laden
    assert updater.herunterladen(paket, str(tmp_path)) == pfad

    github["https://example.invalid/paket.tar.gz"] = b"manipuliert!"
    os.remove(pfad)
    with pytest.raises(updater.UpdateFehler, match="Prüfsumme"):
        updater.herunterladen(paket, str(tmp_path))
    assert os.listdir(tmp_path) == []

    with pytest.raises(updater.UpdateFehler, match="keine Prüfsumme"):
        updater.herunterladen(dict(paket, sha256=""), str(tmp_path))
    with pytest.raises(updater.UpdateFehler, match="Unsicher"):
        updater.herunterladen(dict(paket, url="http://example.invalid/p"), str(tmp_path))


DATEIEN = {"Überzeit-Rechner": b"programm 1.9", "_internal/base_library.zip": b"lib 1.9"}


def _tar(pfad, dateien=None, wurzel="Überzeit-Rechner"):
    with tarfile.open(pfad, "w:gz") as t:
        for name, inhalt in (dateien or DATEIEN).items():
            info = tarfile.TarInfo(f"{wurzel}/{name}" if wurzel else name)
            info.size, info.mode = len(inhalt), 0o755
            t.addfile(info, io.BytesIO(inhalt))
    return str(pfad)


def test_auspacken_tar_und_zip(tmp_path):
    neu = updater.auspacken(_tar(tmp_path / "p.tar.gz"), str(tmp_path / "u"))
    assert sorted(os.listdir(neu)) == ["_internal", "Überzeit-Rechner"]
    assert os.access(os.path.join(neu, "Überzeit-Rechner"), os.X_OK)
    assert sorted(os.listdir(tmp_path / "u")) == ["neu"]

    z = tmp_path / "p.zip"
    with zipfile.ZipFile(z, "w") as f:
        for name, inhalt in DATEIEN.items():
            f.writestr(f"Überzeit-Rechner/{name}", inhalt)
    neu = updater.auspacken(str(z), str(tmp_path / "w"))
    assert open(os.path.join(neu, "_internal", "base_library.zip"), "rb").read() == b"lib 1.9"


def test_auspacken_lehnt_fremde_pakete_ab(tmp_path):
    with pytest.raises(updater.UpdateFehler):
        updater.auspacken(_tar(tmp_path / "a.tar.gz", {"../../boese": b"x"}, wurzel=""),
                          str(tmp_path / "u"))
    with pytest.raises(updater.UpdateFehler, match="_internal"):
        updater.auspacken(_tar(tmp_path / "b.tar.gz", {"nur_eine_datei": b"x"}),
                          str(tmp_path / "u"))
    z = tmp_path / "c.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../ausbruch", b"x")
    with pytest.raises(updater.UpdateFehler, match="Ungültiger Pfad"):
        updater.auspacken(str(z), str(tmp_path / "u"))
    assert not os.path.exists(tmp_path / "ausbruch")


def _programmordner(pfad):
    """Installierte 1.8.1 samt Nutzerdaten."""
    os.makedirs(pfad / "_internal")
    (pfad / "_internal" / "base_library.zip").write_bytes(b"lib 1.8")
    (pfad / "_internal" / "veraltet.so").write_bytes(b"alt")
    (pfad / "Überzeit-Rechner").write_bytes(b"programm 1.8")
    (pfad / "ueberstunden_daten.db").write_bytes(b"DATEN")
    (pfad / "ueberstunden_settings.json").write_text("{}")
    os.makedirs(pfad / "backups")
    return pfad


def test_tauschen_behaelt_daten(tmp_path):
    app = _programmordner(tmp_path / "app")
    neu = updater.auspacken(_tar(tmp_path / "p.tar.gz"), str(app / ".update"))
    updater.tauschen(neu, str(app), str(app / ".update" / "alt"))
    assert (app / "Überzeit-Rechner").read_bytes() == b"programm 1.9"
    # nichts Veraltetes bleibt liegen
    assert sorted(os.listdir(app / "_internal")) == ["base_library.zip"]
    assert (app / "ueberstunden_daten.db").read_bytes() == b"DATEN"
    assert (app / "ueberstunden_settings.json").exists() and (app / "backups").is_dir()
    assert (app / ".update" / "alt" / "Überzeit-Rechner").read_bytes() == b"programm 1.8"

    (app / ".update" / "update.log").write_text("x")
    updater.aufraeumen(str(app / ".update"))
    assert os.listdir(app / ".update") == ["update.log"]


def test_tauschen_zurueck_bei_fehler(tmp_path, monkeypatch):
    app = _programmordner(tmp_path / "app")
    neu = updater.auspacken(_tar(tmp_path / "p.tar.gz"), str(app / ".update"))
    echt = os.rename
    zaehler = [0]

    def rename(a, b):
        zaehler[0] += 1
        if zaehler[0] == 4:          # alte Programmdatei schon weg, neue noch nicht da
            raise PermissionError("gesperrt")
        echt(a, b)

    monkeypatch.setattr(updater.os, "rename", rename)
    with pytest.raises(updater.UpdateFehler, match="alte Version bleibt"):
        updater.tauschen(neu, str(app), str(app / ".update" / "alt"))
    monkeypatch.setattr(updater.os, "rename", echt)
    assert (app / "Überzeit-Rechner").read_bytes() == b"programm 1.8"
    assert (app / "_internal" / "base_library.zip").read_bytes() == b"lib 1.8"
    assert (app / "ueberstunden_daten.db").read_bytes() == b"DATEN"


def test_kann_installieren(tmp_path, monkeypatch):
    assert updater.kann_installieren(str(tmp_path))[0] is False                # Quellcode
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    assert updater.kann_installieren(str(tmp_path)) == (True, "")
    os.chmod(tmp_path, 0o555)
    try:
        if os.access(tmp_path, os.W_OK):
            pytest.skip("läuft als root")
        assert "schreibgeschützt" in updater.kann_installieren(str(tmp_path))[1]
    finally:
        os.chmod(tmp_path, 0o755)


def test_windows_skript_nur_ascii():
    updater._WINDOWS_SKRIPT.encode("ascii")  # pylint: disable=protected-access  # Pfade kommen als Argumente


def test_ssl_kontext_laedt_systemzertifikate(tmp_path, monkeypatch):
    # hier findet OpenSSL selbst welche
    assert netz.ssl_kontext().cert_store_stats()["x509_ca"] > 0
    leer = netz.ssl.create_default_context
    # wie im Bundle: OpenSSL findet nichts
    monkeypatch.setattr(netz.ssl, "create_default_context",
                        lambda: leer(cafile=None, capath=str(tmp_path)))
    assert netz.ssl_kontext(dateien=()).cert_store_stats()["x509_ca"] == 0
    vorhanden = [d for d in netz.SYSTEM_ZERTIFIKATE if os.path.isfile(d)]
    if not vorhanden:
        pytest.skip("keine Systemzertifikate")
    kontext = netz.ssl_kontext(dateien=(str(tmp_path / "fehlt.pem"), vorhanden[0]))
    assert kontext.cert_store_stats()["x509_ca"] > 0
