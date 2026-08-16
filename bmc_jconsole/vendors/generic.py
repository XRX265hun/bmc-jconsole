from __future__ import annotations

from pathlib import Path

from bmc_jconsole.launcher import looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview


class GenericUrlConnector(VendorConnector):
    id = "generic"
    label = "Generic JNLP URL"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        path = host.extra_url.strip()
        if not path:
            raise ConsoleError("Generic vendor needs a JNLP URL in the Extra URL field.")
        response = client.get(path, auth=(host.username, host.password) if host.username else None)
        if response.status_code >= 400:
            raise ConsoleError(f"JNLP download failed HTTP {response.status_code}: {response_preview(response.text)}")
        if not looks_like_jnlp(response.text):
            raise ConsoleError(f"URL did not return a JNLP file: {response_preview(response.text)}")
        return response.text


class LocalJnlpConnector(VendorConnector):
    id = "local"
    label = "Local JNLP file"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        path = Path(host.extra_url).expanduser()
        if not path.is_file():
            raise ConsoleError("Choose a local .jnlp file in Extra URL / Browse JNLP.")
        text = path.read_text(encoding="utf-8", errors="replace")
        if not looks_like_jnlp(text):
            raise ConsoleError(f"{path.name} does not look like a JNLP file.")
        return text
