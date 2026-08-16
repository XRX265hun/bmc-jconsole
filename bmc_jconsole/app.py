from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from bmc_jconsole.connect import connect_host
from bmc_jconsole.launcher import find_javaws
from bmc_jconsole.logutil import write_log
from bmc_jconsole.models import VENDORS, Host
from bmc_jconsole.paste import (
    LAYOUT_KEYS,
    LAYOUT_LABELS,
    PasteError,
    clipboard_text,
    foreground_looks_like_helper,
    start_paste_hotkey,
    type_text,
)
from bmc_jconsole.store import data_dir, load_state, save_state

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VENDOR_LABELS = {key: label for key, label in VENDORS}
VENDOR_KEYS = {label: key for key, label in VENDORS}


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master: App) -> None:
        super().__init__(master)
        self.app = master
        self.title("Settings")
        self.geometry("560x420")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        settings = master.app_state.settings
        pad = {"padx": 16, "pady": 8}

        ctk.CTkLabel(self, text="Java Web Start (javaws)").grid(row=0, column=0, sticky="w", **pad)
        self.javaws_var = tk.StringVar(value=settings.javaws_path)
        ctk.CTkEntry(self, textvariable=self.javaws_var, width=360).grid(row=0, column=1, sticky="ew", **pad)
        ctk.CTkButton(self, text="Browse", width=80, command=self._browse).grid(row=0, column=2, **pad)

        self.verify_var = tk.BooleanVar(value=settings.verify_tls)
        ctk.CTkCheckBox(
            self,
            text="Verify TLS certificates (off for typical self-signed BMCs)",
            variable=self.verify_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", **pad)

        self.remember_var = tk.BooleanVar(value=settings.remember_passwords)
        ctk.CTkCheckBox(
            self,
            text="Remember passwords on this computer (stored in AppData)",
            variable=self.remember_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w", **pad)

        ctk.CTkLabel(self, text="HTTP timeout (seconds)").grid(row=3, column=0, sticky="w", **pad)
        self.timeout_var = tk.StringVar(value=str(settings.timeout_sec))
        ctk.CTkEntry(self, textvariable=self.timeout_var, width=80).grid(row=3, column=1, sticky="w", **pad)

        ctk.CTkLabel(self, text="Paste key delay (ms)").grid(row=4, column=0, sticky="w", **pad)
        self.paste_delay_var = tk.StringVar(value=str(settings.paste_delay_ms))
        ctk.CTkEntry(self, textvariable=self.paste_delay_var, width=80).grid(row=4, column=1, sticky="w", **pad)

        ctk.CTkLabel(self, text="Paste keyboard").grid(row=5, column=0, sticky="w", **pad)
        self.paste_layout_menu = ctk.CTkOptionMenu(
            self,
            values=list(LAYOUT_LABELS.values()),
            width=220,
        )
        self.paste_layout_menu.set(LAYOUT_LABELS.get(settings.paste_layout, LAYOUT_LABELS["us"]))
        self.paste_layout_menu.grid(row=5, column=1, sticky="w", **pad)

        self.paste_hotkey_var = tk.BooleanVar(value=settings.paste_hotkey)
        ctk.CTkCheckBox(
            self,
            text="Ctrl+Alt+V types the clipboard into the focused Java console",
            variable=self.paste_hotkey_var,
        ).grid(row=6, column=0, columnspan=3, sticky="w", **pad)

        hint = (
            "Needs Java 8 with javaws, or OpenWebStart. "
            "Match paste keyboard to the layout selected inside the Java console. "
            f"Config folder: {data_dir()}"
        )
        ctk.CTkLabel(self, text=hint, wraplength=500, text_color="gray").grid(
            row=7, column=0, columnspan=3, sticky="w", **pad
        )

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=8, column=0, columnspan=3, sticky="e", padx=16, pady=16)
        ctk.CTkButton(btns, text="Detect javaws", command=self._detect).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Save", command=self._save).pack(side="left", padx=6)

        self.columnconfigure(1, weight=1)

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select javaws",
            filetypes=[("javaws", "javaws*"), ("All files", "*.*")],
        )
        if path:
            self.javaws_var.set(path)

    def _detect(self) -> None:
        try:
            found = find_javaws(self.javaws_var.get().strip())
            self.javaws_var.set(found)
            self.app.log(f"Found javaws: {found}")
        except Exception as exc:
            messagebox.showerror("javaws", str(exc), parent=self)

    def _save(self) -> None:
        settings = self.app.app_state.settings
        settings.javaws_path = self.javaws_var.get().strip()
        settings.verify_tls = bool(self.verify_var.get())
        settings.remember_passwords = bool(self.remember_var.get())
        try:
            settings.timeout_sec = max(5, int(self.timeout_var.get().strip() or "25"))
        except ValueError:
            settings.timeout_sec = 25
        try:
            settings.paste_delay_ms = max(1, int(self.paste_delay_var.get().strip() or "20"))
        except ValueError:
            settings.paste_delay_ms = 20
        settings.paste_hotkey = bool(self.paste_hotkey_var.get())
        settings.paste_layout = LAYOUT_KEYS.get(self.paste_layout_menu.get(), "us")
        self.app.persist()
        self.app.sync_paste_hotkey()
        self.destroy()


class ConsolePasteDialog(ctk.CTkToplevel):
    def __init__(self, master: App) -> None:
        super().__init__(master)
        self.app = master
        self.title("Console paste")
        self.geometry("560x420")
        self.transient(master)
        pad = {"padx": 16, "pady": 8}

        ctk.CTkLabel(
            self,
            text="Java BMC consoles ignore Ctrl+V. This types keystrokes into the focused console. Set Paste keyboard to the same layout the Java session is using.",
            wraplength=520,
        ).pack(anchor="w", **pad)

        layout_row = ctk.CTkFrame(self, fg_color="transparent")
        layout_row.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(layout_row, text="Paste keyboard").pack(side="left")
        self.layout_menu = ctk.CTkOptionMenu(
            layout_row,
            values=list(LAYOUT_LABELS.values()),
            width=220,
            command=self._layout_changed,
        )
        self.layout_menu.set(LAYOUT_LABELS.get(master.app_state.settings.paste_layout, LAYOUT_LABELS["us"]))
        self.layout_menu.pack(side="left", padx=(8, 0))

        self.body = ctk.CTkTextbox(self, height=200)
        self.body.pack(fill="both", expand=True, padx=16, pady=4)
        try:
            clip = clipboard_text()
        except PasteError:
            clip = ""
        if clip:
            self.body.insert("1.0", clip)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(row, text="Load clipboard", width=140, command=self._load_clipboard).pack(side="left")
        ctk.CTkButton(row, text="Type in 3 seconds", width=170, command=self._countdown).pack(side="right")
        self.status = ctk.CTkLabel(
            self,
            text="Click the Java console, then press Type. Or use Ctrl+Alt+V while the console is focused.",
            text_color="gray",
            wraplength=520,
        )
        self.status.pack(anchor="w", padx=16, pady=(0, 16))

    def _layout_changed(self, label: str) -> None:
        self.app.app_state.settings.paste_layout = LAYOUT_KEYS.get(label, "us")
        self.app.persist()

    def _load_clipboard(self) -> None:
        try:
            text = clipboard_text()
        except PasteError as exc:
            messagebox.showerror("Clipboard", str(exc), parent=self)
            return
        self.body.delete("1.0", "end")
        self.body.insert("1.0", text)

    def _countdown(self, remaining: int = 3) -> None:
        if remaining <= 0:
            self.withdraw()
            self.after(200, self._type_now)
            return
        self.status.configure(text=f"Click the Java console window… typing in {remaining}")
        self.after(1000, lambda: self._countdown(remaining - 1))

    def _type_now(self) -> None:
        if foreground_looks_like_helper():
            self.deiconify()
            self.status.configure(text="The Java console was not focused. Click it, then Type again.")
            return
        text = self.body.get("1.0", "end-1c")
        delay = self.app.app_state.settings.paste_delay_ms
        layout = LAYOUT_KEYS.get(self.layout_menu.get(), self.app.app_state.settings.paste_layout)
        try:
            typed = type_text(text, delay_ms=delay, layout=layout, log=self.app.log)
        except PasteError as exc:
            self.deiconify()
            self.status.configure(text=str(exc))
            messagebox.showerror("Paste", str(exc), parent=self)
            return
        self.destroy()


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("bmc-jconsole")
        self.geometry("980x640")
        self.minsize(860, 540)
        self.app_state = load_state()
        self.selected_id: str | None = None
        self._building = False
        self._stop_paste_hotkey = None

        self._build()
        self.refresh_list()
        if self.app_state.hosts:
            self.select_host(self.app_state.hosts[0].id)
        else:
            self.clear_form()
        self.sync_paste_hotkey()
        self.log("Ready. Add a BMC host, then Connect. Java consoles need javaws (Java 8 or OpenWebStart).")
        self.log("Paste: use Console paste, or Ctrl+Alt+V while the Java window is focused.")

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(top, text="bmc-jconsole", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkLabel(
            top,
            text="Java KVM / AVR / IRC launcher",
            text_color="gray",
        ).pack(side="left", padx=12)
        ctk.CTkButton(top, text="Settings", width=100, command=self.open_settings).pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=8)

        left = ctk.CTkFrame(body, width=280)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="Hosts").pack(anchor="w", padx=12, pady=(12, 4))
        self.listbox = tk.Listbox(
            left,
            bg="#2b2b2b",
            fg="#f0f0f0",
            selectbackground="#1f6aa5",
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 11) if os.name == "nt" else ("DejaVu Sans", 11),
        )
        self.listbox.pack(fill="both", expand=True, padx=12, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.listbox.bind("<Double-Button-1>", lambda _e: self.connect_selected())

        left_btns = ctk.CTkFrame(left, fg_color="transparent")
        left_btns.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(left_btns, text="Add", width=80, command=self.add_host).pack(side="left")
        ctk.CTkButton(left_btns, text="Delete", width=80, fg_color="#8a2d2d", hover_color="#6e2323", command=self.delete_host).pack(side="right")

        right = ctk.CTkFrame(body)
        right.pack(side="left", fill="both", expand=True)
        form = ctk.CTkFrame(right, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=16)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        self.fields: dict[str, tk.Variable] = {}
        self._field(form, "Name", "name", 0, 0)
        self._field(form, "Address", "address", 0, 2)
        self._field(form, "Username", "username", 1, 0)
        self._field(form, "Password", "password", 1, 2, show="*")

        ctk.CTkLabel(form, text="Vendor").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=6)
        self.vendor_menu = ctk.CTkOptionMenu(form, values=[label for _key, label in VENDORS], width=220)
        self.vendor_menu.grid(row=2, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(form, text="Protocol / port").grid(row=2, column=2, sticky="w", padx=(12, 8), pady=6)
        proto_row = ctk.CTkFrame(form, fg_color="transparent")
        proto_row.grid(row=2, column=3, sticky="ew", pady=6)
        self.protocol_menu = ctk.CTkOptionMenu(proto_row, values=["https", "http"], width=90)
        self.protocol_menu.pack(side="left")
        self.port_var = tk.StringVar(value="443")
        ctk.CTkEntry(proto_row, textvariable=self.port_var, width=80).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(form, text="Extra URL / JNLP file").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=6)
        extra_row = ctk.CTkFrame(form, fg_color="transparent")
        extra_row.grid(row=3, column=1, columnspan=3, sticky="ew", pady=6)
        extra_row.columnconfigure(0, weight=1)
        self.extra_var = tk.StringVar()
        ctk.CTkEntry(extra_row, textvariable=self.extra_var).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(extra_row, text="Browse JNLP", width=110, command=self.browse_jnlp).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(form, text="Notes").grid(row=4, column=0, sticky="nw", padx=(0, 8), pady=6)
        self.notes = ctk.CTkTextbox(form, height=70)
        self.notes.grid(row=4, column=1, columnspan=3, sticky="ew", pady=6)

        action = ctk.CTkFrame(right, fg_color="transparent")
        action.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(action, text="Save host", width=120, command=self.save_form).pack(side="left")
        ctk.CTkButton(action, text="Connect", width=140, command=self.connect_selected).pack(side="left", padx=10)
        ctk.CTkButton(action, text="Launch local JNLP", width=160, command=self.launch_local_dialog).pack(side="left")
        ctk.CTkButton(action, text="Console paste", width=130, command=self.open_paste).pack(side="left", padx=10)

        ctk.CTkLabel(right, text="Log").pack(anchor="w", padx=16)
        self.log_box = ctk.CTkTextbox(right, height=180)
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.log_box.configure(state="disabled")

    def _field(self, parent: ctk.CTkFrame, label: str, key: str, row: int, col: int, show: str = "") -> None:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 12, 8), pady=6)
        var = tk.StringVar()
        self.fields[key] = var
        entry = ctk.CTkEntry(parent, textvariable=var, show=show)
        entry.grid(row=row, column=col + 1, sticky="ew", pady=6)

    def log(self, message: str) -> None:
        write_log(message)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def persist(self) -> None:
        save_state(self.app_state)

    def refresh_list(self) -> None:
        self.listbox.delete(0, "end")
        for host in self.app_state.hosts:
            self.listbox.insert("end", host.display_name())
        if self.selected_id:
            for index, host in enumerate(self.app_state.hosts):
                if host.id == self.selected_id:
                    self.listbox.selection_clear(0, "end")
                    self.listbox.selection_set(index)
                    self.listbox.see(index)
                    break

    def _on_list_select(self, _event: object = None) -> None:
        if self._building:
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        host = self.app_state.hosts[selection[0]]
        self.select_host(host.id)

    def select_host(self, host_id: str) -> None:
        host = self.app_state.host_by_id(host_id)
        if host is None:
            return
        self.selected_id = host.id
        self._building = True
        self.fields["name"].set(host.name)
        self.fields["address"].set(host.address)
        self.fields["username"].set(host.username)
        self.fields["password"].set(host.password)
        self.vendor_menu.set(VENDOR_LABELS.get(host.vendor, VENDOR_LABELS["auto"]))
        self.protocol_menu.set(host.protocol or "https")
        self.port_var.set(str(host.port or 443))
        self.extra_var.set(host.extra_url)
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", host.notes)
        self._building = False
        self.refresh_list()

    def clear_form(self) -> None:
        self.selected_id = None
        for var in self.fields.values():
            var.set("")
        self.fields["username"].set("admin")
        self.vendor_menu.set(VENDOR_LABELS["auto"])
        self.protocol_menu.set("https")
        self.port_var.set("443")
        self.extra_var.set("")
        self.notes.delete("1.0", "end")

    def form_to_host(self) -> Host:
        try:
            port = int(self.port_var.get().strip() or "443")
        except ValueError:
            port = 443
        host = self.app_state.host_by_id(self.selected_id or "") or Host.new()
        host.name = self.fields["name"].get().strip()
        host.address = self.fields["address"].get().strip()
        host.username = self.fields["username"].get()
        host.password = self.fields["password"].get()
        host.vendor = VENDOR_KEYS.get(self.vendor_menu.get(), "auto")
        host.protocol = self.protocol_menu.get()
        host.port = port
        host.extra_url = self.extra_var.get().strip()
        host.notes = self.notes.get("1.0", "end").strip()
        return host

    def add_host(self) -> None:
        host = Host.new()
        self.app_state.hosts.append(host)
        self.persist()
        self.select_host(host.id)
        self.log("Added a new host. Fill in address and vendor, then Save.")

    def delete_host(self) -> None:
        if not self.selected_id:
            return
        host = self.app_state.host_by_id(self.selected_id)
        if host is None:
            return
        if not messagebox.askyesno("Delete host", f"Delete {host.display_name()}?"):
            return
        self.app_state.hosts = [item for item in self.app_state.hosts if item.id != host.id]
        self.persist()
        if self.app_state.hosts:
            self.select_host(self.app_state.hosts[0].id)
        else:
            self.clear_form()
            self.refresh_list()
        self.log(f"Deleted {host.display_name()}")

    def save_form(self) -> None:
        host = self.form_to_host()
        existing = self.app_state.host_by_id(host.id)
        if existing is None:
            self.app_state.hosts.append(host)
        self.selected_id = host.id
        self.persist()
        self.refresh_list()
        self.log(f"Saved {host.display_name()}")

    def browse_jnlp(self) -> None:
        path = filedialog.askopenfilename(
            title="Open JNLP",
            filetypes=[("JNLP files", "*.jnlp"), ("All files", "*.*")],
        )
        if not path:
            return
        self.extra_var.set(path)
        if self.vendor_menu.get() == VENDOR_LABELS["auto"]:
            self.vendor_menu.set(VENDOR_LABELS["local"])

    def launch_local_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Launch JNLP",
            filetypes=[("JNLP files", "*.jnlp"), ("All files", "*.*")],
        )
        if not path:
            return
        host = Host.new()
        host.vendor = "local"
        host.extra_url = path
        host.name = "local-jnlp"
        self._connect_async(host)

    def connect_selected(self) -> None:
        host = self.form_to_host()
        if host.vendor != "local" and not host.address:
            messagebox.showwarning("Connect", "Enter a BMC address first.")
            return
        self.save_form()
        self._connect_async(host)

    def _connect_async(self, host: Host) -> None:
        self.log(f"Connecting to {host.display_name()} ({VENDOR_LABELS.get(host.vendor, host.vendor)})...")

        def worker() -> None:
            try:
                message = connect_host(host, self.app_state.settings)
                self.after(0, lambda: self.log(message))
            except Exception as exc:
                text = str(exc)
                self.after(0, lambda: self._connect_failed(text))

        threading.Thread(target=worker, daemon=True).start()

    def _connect_failed(self, text: str) -> None:
        self.log("Connect failed:\n" + text)
        messagebox.showerror("Connect failed", text)

    def open_settings(self) -> None:
        SettingsDialog(self)

    def open_paste(self) -> None:
        ConsolePasteDialog(self)

    def sync_paste_hotkey(self) -> None:
        if self._stop_paste_hotkey is not None:
            self._stop_paste_hotkey()
            self._stop_paste_hotkey = None
        if not self.app_state.settings.paste_hotkey:
            return
        self._stop_paste_hotkey = start_paste_hotkey(lambda: self.after(0, self._hotkey_paste))

    def _hotkey_paste(self) -> None:
        if foreground_looks_like_helper():
            return
        try:
            text = clipboard_text()
            type_text(
                text,
                delay_ms=self.app_state.settings.paste_delay_ms,
                layout=self.app_state.settings.paste_layout,
                log=self.log,
            )
        except PasteError as exc:
            self.log(str(exc))


def main() -> None:
    app = App()
    app.mainloop()
