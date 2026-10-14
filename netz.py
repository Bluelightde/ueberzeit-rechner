"""
HTTPS-Kontext für das gebaute Programm.

PyInstaller bündelt OpenSSL vom Build-Rechner; das sucht die Stammzertifikate dort, wo sie auf
dem Build-Rechner lagen (z. B. /usr/lib/ssl). Auf anderen Linux-Distributionen und unter macOS
findet es dann keine – jede HTTPS-Verbindung scheitert. Hier werden ersatzweise die üblichen
Zertifikatsdateien des Systems geladen. Windows liest den Zertifikatsspeicher des Systems und
braucht das nicht.
"""
import os
import ssl

SYSTEM_ZERTIFIKATE = (
    "/etc/ssl/certs/ca-certificates.crt",                  # Debian, Ubuntu, Arch
    "/etc/pki/tls/certs/ca-bundle.crt",                    # Fedora, RHEL
    "/etc/ssl/ca-bundle.pem",                              # openSUSE
    "/etc/ssl/cert.pem",                                   # macOS, Alpine
)


def ssl_kontext(dateien=SYSTEM_ZERTIFIKATE):
    """SSL-Kontext mit geprüften Zertifikaten.

    Lädt die Zertifikatsdateien des Systems nach, wenn OpenSSL selbst keine findet."""
    kontext = ssl.create_default_context()
    if kontext.cert_store_stats().get("x509_ca", 0):
        return kontext
    for datei in dateien:
        if os.path.isfile(datei):
            try:
                kontext.load_verify_locations(cafile=datei)
                return kontext
            except (ssl.SSLError, OSError):
                continue
    return kontext
