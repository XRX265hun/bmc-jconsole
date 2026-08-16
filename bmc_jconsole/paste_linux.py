from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable

from bmc_jconsole.paste import LAYOUT_LABELS, PasteError

LAYOUT_XKB = {
    "us": ("us", ""),
    "hu": ("hu", ""),
    "hu101": ("hu", "101_qwerty_comma_dead"),
    "de": ("de", ""),
    "gb": ("gb", ""),
    "fr": ("fr", ""),
    "es": ("es", ""),
    "it": ("it", ""),
    "pl": ("pl", ""),
    "cz": ("cz", ""),
    "sk": ("sk", ""),
    "ru": ("ru", ""),
    "se": ("se", ""),
    "nl": ("nl", ""),
    "pt-br": ("br", ""),
}


def clipboard_text() -> str:
    commands = []
    if os.environ.get("WAYLAND_DISPLAY"):
        commands.append(["wl-paste", "-n"])
    commands.extend(
        [
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
            ["wl-paste", "-n"],
        ]
    )
    for cmd in commands:
        if not shutil.which(cmd[0]):
            continue
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=3, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return result.stdout.decode("utf-8", errors="replace")
    raise PasteError(
        "Could not read the clipboard. On Debian install: sudo apt install xclip   "
        "(X11) or sudo apt install wl-clipboard   (Wayland)."
    )


def type_text(
    text: str,
    delay_ms: int = 20,
    layout: str = "us",
    log: Callable[[str], None] | None = None,
) -> int:
    if not text:
        raise PasteError("Nothing to type.")
    chars = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(chars) > 8000:
        raise PasteError("Paste is over 8000 characters. Split it up.")
    delay = max(1, int(delay_ms))
    restored = _push_layout(layout)
    try:
        typed = _type_chars(chars, delay)
    finally:
        if restored:
            restored()
    if log:
        log(f"Typed {typed} characters ({LAYOUT_LABELS.get(layout, layout)}).")
    return typed


def start_paste_hotkey(on_hotkey: Callable[[], None]) -> Callable[[], None]:
    if not os.environ.get("DISPLAY"):
        return lambda: None
    stop = threading.Event()

    def loop() -> None:
        # Poll the focused window's key state via xdotool is not reliable.
        # Use X11 key grab if python3-xlib is absent: bind Ctrl+Alt+v with xbindkeys-like grab
        # through `xdotool` cannot register hotkeys, so we listen with a tiny X helper.
        try:
            _x11_hotkey_loop(on_hotkey, stop)
        except Exception:
            return

    threading.Thread(target=loop, daemon=True, name="bmc-paste-hotkey").start()
    return stop.set


def foreground_looks_like_helper() -> bool:
    title = _active_window_title().lower()
    return "bmc-jconsole" in title or title.startswith("settings") or title.startswith("console paste")


def _active_window_title() -> str:
    if not shutil.which("xdotool"):
        return ""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _type_chars(text: str, delay_ms: int) -> int:
    if shutil.which("xdotool") and os.environ.get("DISPLAY"):
        return _type_xdotool(text, delay_ms)
    if shutil.which("wtype"):
        return _type_wtype(text, delay_ms)
    if shutil.which("ydotool"):
        return _type_ydotool(text, delay_ms)
    raise PasteError(
        "Console paste on Linux needs a typer. On Debian X11: sudo apt install xdotool   "
        "On Wayland: sudo apt install wtype   (or ydotool)."
    )


def _type_xdotool(text: str, delay_ms: int) -> int:
    typed = 0
    buffer: list[str] = []

    def flush() -> None:
        nonlocal typed
        if not buffer:
            return
        chunk = "".join(buffer)
        buffer.clear()
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", str(delay_ms), "--", chunk],
            check=False,
            timeout=120,
        )
        typed += len(chunk)

    for ch in text:
        if ch == "\n":
            flush()
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=False, timeout=5)
            typed += 1
            time.sleep(delay_ms / 1000.0)
        elif ch == "\t":
            flush()
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Tab"], check=False, timeout=5)
            typed += 1
            time.sleep(delay_ms / 1000.0)
        else:
            buffer.append(ch)
            if len(buffer) >= 80:
                flush()
    flush()
    return typed


def _type_wtype(text: str, delay_ms: int) -> int:
    delay = f"{max(1, delay_ms)}ms"
    typed = 0
    for ch in text:
        if ch == "\n":
            subprocess.run(["wtype", "-d", delay, "-k", "Return"], check=False, timeout=5)
        elif ch == "\t":
            subprocess.run(["wtype", "-d", delay, "-k", "Tab"], check=False, timeout=5)
        else:
            subprocess.run(["wtype", "-d", delay, "--", ch], check=False, timeout=5)
        typed += 1
    return typed


def _type_ydotool(text: str, delay_ms: int) -> int:
    subprocess.run(
        ["ydotool", "type", "--key-delay", str(delay_ms), "--", text.replace("\n", "\r")],
        check=False,
        timeout=120,
    )
    return len(text)


def _push_layout(layout: str):
    if not shutil.which("setxkbmap") or not os.environ.get("DISPLAY"):
        return None
    wanted = LAYOUT_XKB.get(layout) or LAYOUT_XKB["us"]
    previous = _xkb_query()
    cmd = ["setxkbmap", wanted[0]]
    if wanted[1]:
        cmd.extend(["-variant", wanted[1]])
    subprocess.run(cmd, check=False, capture_output=True, timeout=3)
    if wanted[1] and previous is not None:
        # Some variants are missing; fall back to the layout name only.
        probe = _xkb_query()
        if probe and probe[0] != wanted[0]:
            subprocess.run(["setxkbmap", wanted[0]], check=False, capture_output=True, timeout=3)
    if previous is None:
        return None

    def restore() -> None:
        old_layout, old_variant = previous
        restore_cmd = ["setxkbmap", old_layout or "us"]
        if old_variant:
            restore_cmd.extend(["-variant", old_variant])
        subprocess.run(restore_cmd, check=False, capture_output=True, timeout=3)

    return restore


def _xkb_query() -> tuple[str, str] | None:
    try:
        result = subprocess.run(
            ["setxkbmap", "-query"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    layout = ""
    variant = ""
    for line in result.stdout.splitlines():
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip().split(",")[0]
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip().split(",")[0]
    return layout, variant


def _x11_hotkey_loop(on_hotkey: Callable[[], None], stop: threading.Event) -> None:
    import ctypes

    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
    except OSError:
        return

    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    display = x11.XOpenDisplay(None)
    if not display:
        return

    ControlMask = 1 << 2
    Mod1Mask = 1 << 3
    LockMask = 1 << 1
    Mod2Mask = 1 << 4
    GrabModeAsync = 1
    XK_v = 0x0076
    XK_V = 0x0056

    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    root = x11.XDefaultRootWindow(display)
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    keycode = x11.XKeysymToKeycode(display, XK_v) or x11.XKeysymToKeycode(display, XK_V)
    if not keycode:
        x11.XCloseDisplay(display)
        return

    modifiers = [
        ControlMask | Mod1Mask,
        ControlMask | Mod1Mask | LockMask,
        ControlMask | Mod1Mask | Mod2Mask,
        ControlMask | Mod1Mask | LockMask | Mod2Mask,
    ]
    x11.XGrabKey.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    for mods in modifiers:
        x11.XGrabKey(display, keycode, mods, root, True, GrabModeAsync, GrabModeAsync)

    class XEvent(ctypes.Structure):
        _fields_ = [("data", ctypes.c_byte * 192)]

    event = XEvent()
    x11.XPending.argtypes = [ctypes.c_void_p]
    x11.XPending.restype = ctypes.c_int
    x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    try:
        while not stop.is_set():
            if x11.XPending(display):
                x11.XNextEvent(display, ctypes.byref(event))
                on_hotkey()
            else:
                time.sleep(0.05)
    finally:
        x11.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
        for mods in modifiers:
            x11.XUngrabKey(display, keycode, mods, root)
        x11.XCloseDisplay(display)
