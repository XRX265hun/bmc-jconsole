from __future__ import annotations

from requests.auth import HTTPDigestAuth

from bmc_jconsole.launcher import looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview


def _require_jnlp(text: str, kind: str) -> str:
    if looks_like_jnlp(text):
        return text
    lowered = text.lower()
    if "html5" in lowered or "<html" in lowered:
        raise ConsoleError(
            f"{kind} returned HTML instead of a Java JNLP. "
            "This iRMC is likely set to the HTML5 viewer, or Java AVR is disabled."
        )
    raise ConsoleError(f"{kind} did not return a JNLP file: {response_preview(text)}")


class IrmcS4Connector(VendorConnector):
    id = "irmc_s4"
    label = "Fujitsu iRMC S2/S3/S4"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        response = client.get(
            "/avr.jnlp",
            auth=HTTPDigestAuth(host.username, host.password),
        )
        if response.status_code == 401:
            response = client.get("/avr.jnlp", auth=(host.username, host.password))
        if response.status_code >= 400:
            raise ConsoleError(f"iRMC S4 AVR download failed HTTP {response.status_code}")
        return _require_jnlp(response.text, "iRMC S4")


class IrmcS5Connector(VendorConnector):
    id = "irmc_s5"
    label = "Fujitsu iRMC S5"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        token = None
        session = client.post(
            "/redfish/v1/SessionService/Sessions",
            json={"UserName": host.username, "Password": host.password},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if session.status_code < 400:
            token = session.headers.get("X-Auth-Token") or session.headers.get("x-auth-token")
        if not token:
            # Some S5 units still honor digest on avr.jnlp.
            fallback = IrmcS4Connector().fetch_jnlp(host, client)
            return fallback
        response = client.get("/avr.jnlp", headers={"X-Auth-Token": token.strip()})
        if response.status_code >= 400:
            raise ConsoleError(f"iRMC S5 AVR download failed HTTP {response.status_code}")
        return _require_jnlp(response.text, "iRMC S5")
