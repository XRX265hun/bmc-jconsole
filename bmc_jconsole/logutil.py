from __future__ import annotations

from datetime import datetime

from bmc_jconsole.store import data_dir


def log_path():
    return data_dir() / "connect.log"


def write_log(message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message.rstrip()}\n"
    with log_path().open("a", encoding="utf-8") as handle:
        handle.write(line)
