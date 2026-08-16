from __future__ import annotations

import os
from collections.abc import Callable

KEYBOARD_LAYOUTS: list[tuple[str, str, str]] = [
    ("us", "English (US)", "00000409"),
    ("hu", "Hungarian", "0000040E"),
    ("hu101", "Hungarian 101-key", "0001040E"),
    ("de", "German", "00000407"),
    ("gb", "English (UK)", "00000809"),
    ("fr", "French", "0000040C"),
    ("es", "Spanish", "0000040A"),
    ("it", "Italian", "00000410"),
    ("pl", "Polish (programmers)", "00000415"),
    ("cz", "Czech", "00000405"),
    ("sk", "Slovak", "0000041B"),
    ("ru", "Russian", "00000419"),
    ("se", "Swedish", "0000041D"),
    ("nl", "Dutch", "00000413"),
    ("pt-br", "Portuguese (Brazil)", "00000416"),
]
LAYOUT_LABELS = {key: label for key, label, _klid in KEYBOARD_LAYOUTS}
LAYOUT_KEYS = {label: key for key, label, _klid in KEYBOARD_LAYOUTS}
LAYOUT_KLIDS = {key: klid for key, _label, klid in KEYBOARD_LAYOUTS}


class PasteError(RuntimeError):
    pass


def _backend():
    if os.name == "nt":
        from bmc_jconsole import paste_win as module
    else:
        from bmc_jconsole import paste_linux as module
    return module


def clipboard_text() -> str:
    return _backend().clipboard_text()


def type_text(
    text: str,
    delay_ms: int = 20,
    layout: str = "us",
    log: Callable[[str], None] | None = None,
) -> int:
    return _backend().type_text(text, delay_ms=delay_ms, layout=layout, log=log)


def start_paste_hotkey(on_hotkey: Callable[[], None]) -> Callable[[], None]:
    return _backend().start_paste_hotkey(on_hotkey)


def foreground_looks_like_helper() -> bool:
    return _backend().foreground_looks_like_helper()
