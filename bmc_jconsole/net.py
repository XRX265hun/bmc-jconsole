from __future__ import annotations

import ssl
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter

from bmc_jconsole.models import Host

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Old BMCs speak TLS 1.0/1.1, DHE, and unsafe renegotiation.
# A modern OpenSSL client fails with handshake_failure until this is set.
_LEGACY_CIPHERS = "ALL:@SECLEVEL=0"


def make_legacy_ssl_context(verify_tls: bool) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED if verify_tls else ssl.CERT_NONE
    if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
        context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    try:
        context.set_ciphers(_LEGACY_CIPHERS)
    except ssl.SSLError:
        context.set_ciphers("DEFAULT:@SECLEVEL=0")
    for version in (
        getattr(ssl.TLSVersion, "MINIMUM_SUPPORTED", None),
        getattr(ssl.TLSVersion, "TLSv1", None),
    ):
        if version is None:
            continue
        try:
            context.minimum_version = version
            break
        except (ValueError, OSError):
            continue
    return context


class LegacyHTTPSAdapter(HTTPAdapter):
    def __init__(self, verify_tls: bool, **kwargs: Any) -> None:
        self._verify_tls = verify_tls
        super().__init__(**kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["ssl_context"] = make_legacy_ssl_context(self._verify_tls)
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["ssl_context"] = make_legacy_ssl_context(self._verify_tls)
        return super().proxy_manager_for(*args, **kwargs)


class HttpError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, host: Host, timeout: int, verify_tls: bool) -> None:
        self.host = host
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_tls
        self.session.mount("https://", LegacyHTTPSAdapter(verify_tls))
        self.session.headers.update(
            {
                "User-Agent": "bmc-jconsole/0.1",
                "Accept": "*/*",
            }
        )

    def url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.host.base_url() + path

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            return self.session.get(self.url(path), **kwargs)
        except requests.RequestException as exc:
            raise HttpError(f"GET {path} failed: {exc}") from exc

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            return self.session.post(self.url(path), **kwargs)
        except requests.RequestException as exc:
            raise HttpError(f"POST {path} failed: {exc}") from exc
