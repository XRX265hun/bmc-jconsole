from __future__ import annotations

from bmc_jconsole.logutil import write_log
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector
from bmc_jconsole.vendors.generic import GenericUrlConnector, LocalJnlpConnector
from bmc_jconsole.vendors.idrac import IdracConnector
from bmc_jconsole.vendors.ilo import IloConnector
from bmc_jconsole.vendors.imm import ImmConnector
from bmc_jconsole.vendors.irmc import IrmcS4Connector, IrmcS5Connector
from bmc_jconsole.vendors.supermicro import SupermicroConnector

CONNECTORS: dict[str, VendorConnector] = {
    "irmc_s4": IrmcS4Connector(),
    "irmc_s5": IrmcS5Connector(),
    "idrac": IdracConnector(),
    "ilo": IloConnector(),
    "supermicro": SupermicroConnector(),
    "imm": ImmConnector(),
    "generic": GenericUrlConnector(),
    "local": LocalJnlpConnector(),
}

AUTO_ORDER = ("ilo", "irmc_s4", "irmc_s5", "supermicro", "idrac", "imm")


def detect_vendor(host: Host, client: HttpClient) -> str | None:
    try:
        probe = client.get("/json/login_session")
        text = probe.text.lower()
        if probe.status_code == 200 and any(
            token in text for token in ("secjmp", "ilo_fw", '"cn":', "license_directory_auth")
        ):
            write_log(f"{host.address}: fingerprint iLO via /json/login_session")
            return "ilo"
    except Exception:
        pass
    try:
        home = client.get("/")
        text = home.text.lower()
        if "integrated lights-out" in text or "ilo.js" in text or "hp proliant" in text:
            write_log(f"{host.address}: fingerprint iLO via /")
            return "ilo"
        if "irmc" in text or "fujitsu" in text:
            return "irmc_s4"
        if "idrac" in text or "dell remote access" in text:
            return "idrac"
        if "supermicro" in text or "atenn" in text or "ikvm" in text:
            return "supermicro"
        if "integrated management module" in text or ">imm<" in text:
            return "imm"
    except Exception:
        pass
    return None


class AutoConnector(VendorConnector):
    id = "auto"
    label = "Auto-detect"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        errors: list[str] = []
        detected = detect_vendor(host, client)
        order = []
        if detected:
            order.append(detected)
        for vendor_id in AUTO_ORDER:
            if vendor_id not in order:
                order.append(vendor_id)
        for vendor_id in order:
            attempt = HttpClient(host, timeout=client.timeout, verify_tls=client.session.verify)
            try:
                write_log(f"{host.address}: trying vendor {vendor_id}")
                return CONNECTORS[vendor_id].fetch_jnlp(host, attempt)
            except Exception as exc:  # noqa: BLE001 - collect and try the next vendor
                errors.append(f"{vendor_id}: {exc}")
                write_log(f"{host.address}: {vendor_id} failed: {exc}")
        raise ConsoleError("Auto-detect could not fetch a Java console.\n" + "\n".join(errors))


CONNECTORS["auto"] = AutoConnector()


def fetch_jnlp(host: Host, client: HttpClient) -> str:
    connector = CONNECTORS.get(host.vendor)
    if connector is None:
        raise ConsoleError(f"Unknown vendor: {host.vendor}")
    return connector.fetch_jnlp(host, client)
