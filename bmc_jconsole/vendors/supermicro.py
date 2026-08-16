from __future__ import annotations

import re

from bmc_jconsole.launcher import looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview


class SupermicroConnector(VendorConnector):
    id = "supermicro"
    label = "SuperMicro iKVM"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        errors: list[str] = []
        verify = client.session.verify
        timeout = client.timeout

        aten = self._aten(host, HttpClient(host, timeout=timeout, verify_tls=verify))
        if looks_like_jnlp(aten):
            return aten
        if aten:
            errors.append(aten)

        ami = self._ami(host, HttpClient(host, timeout=timeout, verify_tls=verify))
        if looks_like_jnlp(ami):
            return ami
        if ami:
            errors.append(ami)

        raise ConsoleError("SuperMicro Java console download failed. " + " | ".join(errors))

    def _aten(self, host: Host, client: HttpClient) -> str:
        login = client.post(
            "/cgi/login.cgi",
            data={"name": host.username, "pwd": host.password},
            headers={"Referer": client.url("/")},
        )
        if login.status_code >= 400:
            return f"ATEN login HTTP {login.status_code}"
        for path in (
            "/cgi/url_redirect.cgi?url_name=ikvm&url_type=jwsk",
            "/cgi/url_redirect.cgi?url_name=man_ikvm&url_type=jwsk",
        ):
            response = client.get(path, headers={"Referer": client.url("/")})
            if response.status_code < 400 and looks_like_jnlp(response.text):
                return response.text
        return f"ATEN JNLP not found: {response_preview(login.text)}"

    def _ami(self, host: Host, client: HttpClient) -> str:
        login = client.post(
            "/rpc/WEBSES/create.asp",
            data={"WEBVAR_USERNAME": host.username, "WEBVAR_PASSWORD": host.password},
        )
        if login.status_code >= 400:
            return f"AMI login HTTP {login.status_code}"
        match = re.search(r"SESSION_COOKIE'\s*,\s*'([^']+)'", login.text)
        if not match:
            match = re.search(r"SESSION_COOKIE[^\n'\"]+['\"]([^'\"]+)", login.text)
        if match:
            client.session.cookies.set("SessionCookie", match.group(1))
        path = f"/Java/jviewer.jnlp?EXTRNIP={host.address}&JNLPSTR=JViewer"
        response = client.get(path)
        if response.status_code < 400 and looks_like_jnlp(response.text):
            return response.text
        return f"AMI JNLP not found: {response_preview(response.text)}"
