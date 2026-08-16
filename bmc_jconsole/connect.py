from __future__ import annotations

import json

from bmc_jconsole.launcher import find_javaws, launch_ilo_applet, launch_jnlp, launch_stem, write_jnlp
from bmc_jconsole.logutil import write_log
from bmc_jconsole.models import Host, Settings
from bmc_jconsole.net import HttpClient
from bmc_jconsole.store import cache_dir
from bmc_jconsole.vendors import fetch_jnlp


def connect_host(host: Host, settings: Settings) -> str:
    if not host.address.strip() and host.vendor != "local":
        raise ValueError("Host address is empty.")
    write_log(f"connect start host={host.address} vendor={host.vendor} proto={host.protocol}:{host.port}")
    try:
        client = HttpClient(host, timeout=settings.timeout_sec, verify_tls=settings.verify_tls)
        jnlp = fetch_jnlp(host, client)
        stem = launch_stem(host.name or host.address or "console")
        path = write_jnlp(jnlp, stem)
        write_log(f"wrote {path} ({path.stat().st_size} bytes)")
        plan_path = cache_dir() / f"{stem}.launch.json"
        if plan_path.is_file():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if plan.get("mode") == "ilo-applet":
                launch_ilo_applet(plan, settings.javaws_path)
                write_log(f"launched iLO applet codebase={plan.get('codebase')}")
                return f"Launched iLO Java IRC applet against {plan.get('codebase')}"
        javaws = find_javaws(settings.javaws_path)
        write_log(f"javaws={javaws}")
        launch_jnlp(path, javaws)
        write_log(f"launched {path.name}")
        return f"Launched {path.name} with {javaws}"
    except Exception as exc:
        write_log(f"connect failed: {exc}")
        raise
