from __future__ import annotations

import json
import os
from pathlib import Path

from bmc_jconsole.models import AppState, Host, Settings


def data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = root / "bmc-jconsole"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return data_dir() / "state.json"


def load_state() -> AppState:
    path = _state_path()
    if not path.exists():
        return AppState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppState()
    settings = Settings.from_dict(raw.get("settings") or {})
    hosts = [Host.from_dict(item) for item in raw.get("hosts") or []]
    if not settings.remember_passwords:
        for host in hosts:
            host.password = ""
    return AppState(settings=settings, hosts=hosts)


def save_state(state: AppState) -> None:
    payload = {
        "settings": state.settings.to_dict(),
        "hosts": [],
    }
    for host in state.hosts:
        item = host.to_dict()
        if not state.settings.remember_passwords:
            item["password"] = ""
        payload["hosts"].append(item)
    path = _state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
