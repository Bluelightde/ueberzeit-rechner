"""
Umgebung für Systemprogramme (journalctl, last, who, PowerShell, hdiutil …) aus der gebauten App.

PyInstaller setzt im gebauten Programm LD_LIBRARY_PATH (macOS: DYLD_LIBRARY_PATH) auf den eigenen
Ordner _internal, damit es seine mitgelieferten Bibliotheken findet. Unterprogramme erben das und
laden dann z. B. das mitgelieferte, ältere libcrypto statt dem des Systems -- journalctl bricht
mit „version OPENSSL_3.4.0 not found“ ab, und die Anmeldezeit fehlt (1.9.0/1.9.1). Den
ursprünglichen Wert hebt PyInstaller unter *_ORIG auf. Nur Standardbibliothek, ohne Qt.
"""
import os
import sys

_PFADE = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")


def system_env(basis=None, **extra):
    """Kopie der Umgebung ohne Bibliothekspfade des Bundles, plus extra (z. B. LC_ALL="C")."""
    env = dict(os.environ if basis is None else basis)
    if getattr(sys, "frozen", False):
        for name in _PFADE:
            ursprung = env.pop(name + "_ORIG", None)
            if ursprung is not None:
                env[name] = ursprung
            else:
                env.pop(name, None)
    env.update(extra)
    return env
