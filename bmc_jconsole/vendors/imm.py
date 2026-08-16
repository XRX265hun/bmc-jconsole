from __future__ import annotations

from bmc_jconsole.launcher import looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview


class ImmConnector(VendorConnector):
    id = "imm"
    label = "Lenovo IMM"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        login = client.post(
            "/data/login",
            data={"user": host.username, "password": host.password},
        )
        if login.status_code >= 400:
            raise ConsoleError(f"IMM login failed HTTP {login.status_code}: {response_preview(login.text)}")
        paths = [
            "/designs/imm/viewer.jnlp",
            "/viewer.jnlp",
            "/designs/imm/jviewer.jnlp",
        ]
        for path in paths:
            response = client.get(path)
            if response.status_code < 400 and looks_like_jnlp(response.text):
                return response.text
        raise ConsoleError("IMM did not return a Java viewer JNLP")
