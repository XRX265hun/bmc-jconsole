from __future__ import annotations

from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient


class ConsoleError(RuntimeError):
    pass


class VendorConnector:
    id = ""
    label = ""

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        raise NotImplementedError


def response_preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."
