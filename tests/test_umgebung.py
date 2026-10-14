"""system_env(): Systemprogramme aus der gebauten App ohne die Bibliotheken des Bundles starten."""
# pylint: disable=missing-function-docstring
import shutil
import subprocess
import sys

import pytest

import umgebung


def test_im_bundle_ursprung_zurueck(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = umgebung.system_env({"LD_LIBRARY_PATH": "/app/_internal", "PATH": "/usr/bin"},
                              LC_ALL="C")
    assert "LD_LIBRARY_PATH" not in env and env["PATH"] == "/usr/bin" and env["LC_ALL"] == "C"
    env = umgebung.system_env({"LD_LIBRARY_PATH": "/app/_internal",
                               "LD_LIBRARY_PATH_ORIG": "/opt/lib"})
    assert env["LD_LIBRARY_PATH"] == "/opt/lib" and "LD_LIBRARY_PATH_ORIG" not in env


def test_aus_dem_quelltext_unveraendert(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert umgebung.system_env({"LD_LIBRARY_PATH": "/x"})["LD_LIBRARY_PATH"] == "/x"


@pytest.mark.skipif(not shutil.which("journalctl"), reason="ohne journalctl")
def test_journalctl_trotz_fremder_bibliotheken(monkeypatch, tmp_path):
    """Ein Bundle-Ordner mit unbrauchbarem libcrypto bricht journalctl -- system_env() nicht."""
    (tmp_path / "libcrypto.so.3").write_bytes(b"kaputt")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", str(tmp_path))
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    kaputt = subprocess.run(["journalctl", "--version"], capture_output=True, check=False)
    heil = subprocess.run(["journalctl", "--version"], capture_output=True, check=False,
                          env=umgebung.system_env())
    assert kaputt.returncode != 0
    assert heil.returncode == 0
