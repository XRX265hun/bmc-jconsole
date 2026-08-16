from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import quoteattr

from bmc_jconsole.launcher import launch_stem, looks_like_jnlp
from bmc_jconsole.models import Host
from bmc_jconsole.net import HttpClient
from bmc_jconsole.store import cache_dir
from bmc_jconsole.vendors.base import ConsoleError, VendorConnector, response_preview

_PARAM_RE = re.compile(
    r'PARAM\s+name=(?:\\")?(?P<name>[A-Za-z0-9_]+)(?:\\")?\s+VALUE=(?:\\")(?P<value>.*?)(?:\\")',
    re.I,
)
_EMBED_RE = re.compile(
    r'\b(?P<name>RCINFO[A-Z0-9]*|INFO\d+|INTGTITLE|RCINFOLANG)\s*=\s*(?:\\")(?P<value>.*?)(?:\\")',
    re.I,
)
_JAR_RE = re.compile(r'archive\s*=\s*"?/?([^"\s>]+\.jar)"?', re.I)
_CODE_RE = re.compile(r'\bcode\s*=\s*"([^"]+)"', re.I)


def _parse_applet(html: str) -> tuple[str, str, dict[str, str]]:
    params: dict[str, str] = {}
    for match in _PARAM_RE.finditer(html):
        value = match.group("value")
        if "+skey+" in value or "+rport+" in value or "+langId+" in value:
            continue
        params[match.group("name")] = value
    if len(params) < 3:
        for match in _EMBED_RE.finditer(html):
            value = match.group("value")
            if "+skey+" in value or "+rport+" in value or "+langId+" in value:
                continue
            params.setdefault(match.group("name"), value)
    jar_match = _JAR_RE.search(html)
    code_match = _CODE_RE.search(html)
    jar = jar_match.group(1) if jar_match else "html/intgapp3_231.jar"
    code = code_match.group(1) if code_match else "com.hp.ilo2.intgapp.intgapp.class"
    if jar.startswith("html/"):
        pass
    elif not jar.startswith("/"):
        jar = "html/" + jar
    return jar, code, params


def _applet_jnlp(codebase: str, jar_name: str, main_class: str, params: dict[str, str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<jnlp spec="1.0+" codebase={quoteattr(codebase)}>',
        "  <information>",
        "    <title>HP iLO Java Integrated Remote Console</title>",
        "    <vendor>Hewlett Packard Enterprise</vendor>",
        "    <offline-allowed/>",
        "  </information>",
        "  <security><all-permissions/></security>",
        "  <resources>",
        '    <j2se version="1.6+"/>',
        f"    <jar href={quoteattr(jar_name)} main=\"true\"/>",
        "  </resources>",
        f'  <applet-desc name="INTGAPP" main-class={quoteattr(main_class)} width="1024" height="768">',
    ]
    for name, value in params.items():
        lines.append(f"    <param name={quoteattr(name)} value={quoteattr(value)}/>")
    lines.append("  </applet-desc>")
    lines.append("</jnlp>")
    return "\n".join(lines) + "\n"


class IloConnector(VendorConnector):
    id = "ilo"
    label = "HPE iLO 3/4 (Java IRC)"

    def fetch_jnlp(self, host: Host, client: HttpClient) -> str:
        login = client.post(
            "/json/login_session",
            json={
                "method": "login",
                "user_login": host.username,
                "password": host.password,
            },
            headers={"Content-Type": "application/json"},
        )
        if login.status_code >= 400:
            raise ConsoleError(f"iLO login failed HTTP {login.status_code}: {response_preview(login.text)}")

        session_key = ""
        try:
            body = login.json()
            session_key = str(body.get("session_key") or body.get("sessionKey") or "")
            if body.get("remote_cons_priv") == 0:
                raise ConsoleError("iLO login succeeded but this account has no remote console privilege.")
        except ValueError:
            session_key = ""
        if not session_key:
            raise ConsoleError(f"iLO login did not return a session key: {response_preview(login.text)}")
        client.session.cookies.set("sessionKey", session_key)

        headers = {"Accept": "application/x-java-jnlp-file, application/xml, text/xml, text/html, */*"}
        for path in (
            f"/html/java_irc.html?sessionKey={session_key}",
            "/html/java_irc.jnlp",
            "/html/jirc.jnlp",
            "/html/IRC.jnlp",
        ):
            response = client.get(path, headers=headers)
            if response.status_code >= 400:
                continue
            if looks_like_jnlp(response.text):
                return response.text
            if "intgapp" in response.text.lower() or "applet" in response.text.lower():
                return self._jnlp_from_applet_page(host, client, response.text, session_key)

        raise ConsoleError(
            "iLO logged in but no Java IRC applet/JNLP was found. "
            "This firmware may only offer HTML5, or Java IRC is disabled."
        )

    def _jnlp_from_applet_page(
        self,
        host: Host,
        client: HttpClient,
        html: str,
        session_key: str,
    ) -> str:
        jar_path, code, params = _parse_applet(html)
        if not params.get("RCINFO1"):
            params["RCINFO1"] = session_key
        params["RCINFOLANG"] = "en"
        main_class = code.removesuffix(".class")
        jar_url = jar_path if jar_path.startswith("/") else "/" + jar_path
        jar_name = Path(jar_path).name
        stem = launch_stem(host.name or host.address)
        local_name = f"{stem}_{jar_name}"
        jar_response = client.get(jar_url)
        if jar_response.status_code >= 400 or len(jar_response.content) < 1000:
            raise ConsoleError(
                f"Could not download iLO Java IRC jar {jar_url} "
                f"(HTTP {jar_response.status_code}, {len(jar_response.content)} bytes)."
            )
        jar_file = cache_dir() / local_name
        jar_file.write_bytes(jar_response.content)
        codebase = host.base_url().rstrip("/") + "/html/"
        documentbase = host.base_url().rstrip("/") + "/html/java_irc.html"
        plan = {
            "mode": "ilo-applet",
            "jar": str(jar_file),
            "main_class": main_class,
            "codebase": codebase,
            "documentbase": documentbase,
            "params": params,
        }
        (cache_dir() / f"{stem}.launch.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return _applet_jnlp(codebase, jar_name, main_class, params)
