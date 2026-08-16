from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Callable
from ctypes import wintypes

from bmc_jconsole.paste import LAYOUT_KLIDS, LAYOUT_LABELS, PasteError

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SPACE = 0x20
MAPVK_VK_TO_VSC = 0
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 0xB1C0
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", INPUTUNION)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def _user32():
    return ctypes.windll.user32


def clipboard_text() -> str:
    cf_unicode = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        raise PasteError("Could not read the clipboard.")
    try:
        handle = user32.GetClipboardData(cf_unicode)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return ""
        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def type_text(
    text: str,
    delay_ms: int = 20,
    layout: str = "us",
    log: Callable[[str], None] | None = None,
) -> int:
    if not text:
        raise PasteError("Nothing to type.")
    delay = max(1, int(delay_ms)) / 1000.0
    chars = _normalize(text)
    if len(chars) > 8000:
        raise PasteError("Paste is over 8000 characters. Split it up.")
    hkl = _layout_handle(layout)
    _release_modifiers()
    _ensure_caps_off()
    typed = 0
    skipped = 0
    for ch in chars:
        mapped = _vk_for_char(ch, hkl)
        if mapped is None:
            skipped += 1
            continue
        vk, shift, ctrl, alt, extended = mapped
        _tap(vk, shift=shift, ctrl=ctrl, alt=alt, extended=extended, hkl=hkl)
        typed += 1
        time.sleep(delay)
    if log:
        extra = f", skipped {skipped} unsupported characters" if skipped else ""
        log(f"Typed {typed} characters ({LAYOUT_LABELS.get(layout, layout)}){extra}.")
    return typed


def start_paste_hotkey(on_hotkey: Callable[[], None]) -> Callable[[], None]:
    user32 = ctypes.windll.user32
    stop = threading.Event()

    def loop() -> None:
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("V")):
            return
        msg = MSG()
        try:
            while not stop.is_set():
                got = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
                if got and msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    on_hotkey()
                elif not got:
                    time.sleep(0.05)
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)

    threading.Thread(target=loop, daemon=True, name="bmc-paste-hotkey").start()
    return stop.set


def foreground_looks_like_helper() -> bool:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(max(length, 8))
    user32.GetWindowTextW(hwnd, buf, len(buf))
    title = buf.value.lower()
    return "bmc-jconsole" in title or title.startswith("settings") or title.startswith("console paste")


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r")


def _layout_handle(layout: str) -> int:
    user32 = _user32()
    klid = LAYOUT_KLIDS.get(layout) or LAYOUT_KLIDS["us"]
    hkl = user32.LoadKeyboardLayoutW(klid, 0)
    if not hkl:
        raise PasteError(
            f"Windows could not load the {LAYOUT_LABELS.get(layout, layout)} keyboard. "
            "Install that layout in Windows Settings, or switch paste language to English (US)."
        )
    return hkl


def _vk_for_char(ch: str, hkl: int) -> tuple[int, bool, bool, bool, bool] | None:
    if ch == "\r":
        return VK_RETURN, False, False, False, False
    if ch == "\t":
        return VK_TAB, False, False, False, False
    if ch == " ":
        return VK_SPACE, False, False, False, False
    if ch == "\b":
        return VK_BACK, False, False, False, False
    if ord(ch) < 32:
        return None

    user32 = _user32()
    packed = ctypes.c_short(user32.VkKeyScanExW(ctypes.c_wchar(ch), hkl)).value
    if packed == -1:
        return None
    vk = packed & 0xFF
    if vk == 0xFF:
        return None
    shift = bool(packed & 0x100)
    ctrl = bool(packed & 0x200)
    alt = bool(packed & 0x400)
    extended = vk in {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}
    return vk, shift, ctrl, alt, extended


def _tap(
    vk: int,
    shift: bool = False,
    ctrl: bool = False,
    alt: bool = False,
    extended: bool = False,
    hkl: int = 0,
) -> None:
    if ctrl:
        _key(VK_CONTROL, down=True, hkl=hkl)
    if alt:
        _key(VK_MENU, down=True, hkl=hkl)
    if shift:
        _key(VK_SHIFT, down=True, hkl=hkl)
    _key(vk, down=True, extended=extended, hkl=hkl)
    _key(vk, down=False, extended=extended, hkl=hkl)
    if shift:
        _key(VK_SHIFT, down=False, hkl=hkl)
    if alt:
        _key(VK_MENU, down=False, hkl=hkl)
    if ctrl:
        _key(VK_CONTROL, down=False, hkl=hkl)


def _key(vk: int, down: bool, extended: bool = False, hkl: int = 0) -> None:
    user32 = _user32()
    if hkl:
        scan = user32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC, hkl)
    else:
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = 0
    if not down:
        flags |= KEYEVENTF_KEYUP
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.ii.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if sent != 1:
        raise PasteError("Windows refused the keystroke (SendInput failed).")


def _release_modifiers() -> None:
    user32 = _user32()
    for vk in (VK_SHIFT, VK_CONTROL, VK_MENU):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            _key(vk, down=False)


def _ensure_caps_off() -> None:
    user32 = _user32()
    if user32.GetKeyState(VK_CAPITAL) & 1:
        _key(VK_CAPITAL, down=True)
        _key(VK_CAPITAL, down=False)
