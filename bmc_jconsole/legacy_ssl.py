from __future__ import annotations

from pathlib import Path

from bmc_jconsole.store import data_dir

LEGACY_SECURITY = """\
# Overlay for Java 8 talking to old BMCs (iLO 3 TLS 1.1 / DHE).
jdk.tls.disabledAlgorithms=SSLv3, RC4, DES, MD5withRSA, DH keySize < 768, EC keySize < 224, anon, NULL
jdk.certpath.disabledAlgorithms=MD2, MD5
jdk.jar.disabledAlgorithms=MD2, MD5, RSA keySize < 1024
"""


def legacy_security_file() -> Path:
    path = data_dir() / "legacy-java.security"
    path.write_text(LEGACY_SECURITY, encoding="ascii")
    return path
