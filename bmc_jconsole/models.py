from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

VENDORS: list[tuple[str, str]] = [
    ("auto", "Auto-detect"),
    ("irmc_s4", "Fujitsu iRMC S2/S3/S4 (Java AVR)"),
    ("irmc_s5", "Fujitsu iRMC S5 (Java AVR)"),
    ("idrac", "Dell iDRAC 6/7/8"),
    ("ilo", "HPE iLO 3/4 (Java IRC applet)"),
    ("supermicro", "SuperMicro iKVM / MegaRAC"),
    ("imm", "Lenovo IMM / IMM2"),
    ("generic", "Generic JNLP URL"),
    ("local", "Local JNLP file (no login)"),
]


@dataclass
class Host:
    id: str
    name: str
    address: str
    vendor: str = "auto"
    username: str = "admin"
    password: str = ""
    port: int = 443
    protocol: str = "https"
    extra_url: str = ""
    notes: str = ""

    @classmethod
    def new(cls) -> Host:
        return cls(id=str(uuid4()), name="New host", address="")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Host:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        if "id" not in known:
            known["id"] = str(uuid4())
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def display_name(self) -> str:
        label = self.name.strip() or self.address or "(unnamed)"
        if self.address and self.address not in label:
            return f"{label}  ({self.address})"
        return label

    def base_url(self) -> str:
        default_port = 443 if self.protocol == "https" else 80
        if self.port and self.port != default_port:
            return f"{self.protocol}://{self.address}:{self.port}"
        return f"{self.protocol}://{self.address}"


@dataclass
class Settings:
    javaws_path: str = ""
    verify_tls: bool = False
    timeout_sec: int = 25
    remember_passwords: bool = True
    paste_delay_ms: int = 20
    paste_hotkey: bool = True
    paste_layout: str = "us"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        layout = str(data.get("paste_layout", "us") or "us")
        from bmc_jconsole.paste import LAYOUT_KLIDS

        if layout not in LAYOUT_KLIDS:
            layout = "us"
        return cls(
            javaws_path=str(data.get("javaws_path", "")),
            verify_tls=bool(data.get("verify_tls", False)),
            timeout_sec=int(data.get("timeout_sec", 25) or 25),
            remember_passwords=bool(data.get("remember_passwords", True)),
            paste_delay_ms=int(data.get("paste_delay_ms", 20) or 20),
            paste_hotkey=bool(data.get("paste_hotkey", True)),
            paste_layout=layout,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AppState:
    settings: Settings = field(default_factory=Settings)
    hosts: list[Host] = field(default_factory=list)

    def host_by_id(self, host_id: str) -> Host | None:
        for host in self.hosts:
            if host.id == host_id:
                return host
        return None
