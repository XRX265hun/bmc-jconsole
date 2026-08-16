from __future__ import annotations

import time

from bmc_jconsole.launcher import looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview


class IdracConnector(VendorConnector):
    id = "idrac"
    label = "Dell iDRAC"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        login = None
        for payload in (
            {"user": host.username, "password": host.password},
            {"userName": host.username, "password": host.password},
        ):
            login = client.post("/data/login", data=payload)
            if login.status_code < 400 and "authresult>1" not in login.text.lower():
                break
        if login is None or login.status_code >= 400:
            basic = client.get("/Software/jviewer.jnlp", auth=(host.username, host.password))
            if looks_like_jnlp(basic.text):
                return basic.text
            raise ConsoleError(
                f"iDRAC login failed HTTP {login.status_code if login else '?'}: "
                f"{response_preview(login.text if login else '')}"
            )

        stamp = int(time.time() * 1000)
        paths = [
            "/viewer.jnlp",
            f"/viewer.jnlp(0@{host.address}@{stamp})",
            f"/viewer.jnlp(1@{host.address}@{stamp})",
            "/Software/jviewer.jnlp",
            "/Applications/dellVirtualConsole.jnlp",
        ]
        last_error = "no JNLP URL succeeded"
        for path in paths:
            response = client.get(path)
            if response.status_code < 400 and looks_like_jnlp(response.text):
                return response.text
            last_error = f"HTTP {response.status_code} from {path}: {response_preview(response.text)}"
        raise ConsoleError(f"iDRAC did not return a Java viewer JNLP ({last_error})")
