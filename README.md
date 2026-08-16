# bmc-jconsole

Desktop helper for **Java (non-HTML5)** server consoles: Fujitsu iRMC AVR, Dell iDRAC, HPE iLO Java IRC, SuperMicro iKVM, and Lenovo IMM.

It logs into the BMC, fetches a fresh viewer (`.jnlp` or the iLO 3 applet), and launches it so you do not have to click through the web UI every time.

Used ProLiant, iRMC, iDRAC, and SuperMicro boxes still show up in homelabs and technical-school racks. The cheap hardware is fine; the Java console in a modern browser is the part that wastes an afternoon. This helper is for that.

This project is open source under the [MIT License](LICENSE). It is not affiliated with Hewlett Packard, Dell, Fujitsu, Super Micro, or Lenovo.

**This is vibe-coded.** It was written with [Cursor](https://cursor.com) as a pair programmer (yes, the `Cursor` co-author on commits is that). Treat it as a lab helper, not a vendor product. Live testing so far is mainly **HP iLO 3**; other BMC paths are included because those Java consoles still exist, not because every one was proven here. If something is wrong, open an issue or a PR — that is more useful than being angry that an AI helped write it.

## Requirements

- Python 3.10+ (on Debian: `python3`, `python3-venv`, `python3-tk`)
- **Java 8** for iLO 3 applet hosting, plus **Java Web Start** (`javaws` / [IcedTea-Web](https://icedtea.classpath.org/wiki/IcedTea-Web) / [OpenWebStart](https://openwebstart.com/))
- Network reachability to the BMC (self-signed TLS is accepted by default)
- Console paste on Linux: `xdotool` + `xclip` (X11) or `wtype` + `wl-clipboard` (Wayland)

Modern Oracle Java 11+ does **not** include Web Start. Use an 8u JRE, IcedTea-Web, or OpenWebStart.

Old BMCs (iLO 3, iRMC S2–S4, iDRAC 6, etc.) often only speak **TLS 1.0/1.1** with weak DHE ciphers. This app uses a legacy TLS client for that. iLO 3 Java IRC is an **applet** (`intgapp*.jar`), not a `.jnlp` download — the app hosts that applet after login.

## Download

Get a zip from **[Releases](https://github.com/XRX265hun/bmc-jconsole/releases)** (Source code) and unzip it.

**Windows:** double-click `start.bat`.

**Debian / Linux:**

```bash
sudo apt install python3 python3-venv python3-tk python3-pip xdotool xclip
# Java Web Start:
sudo apt install icedtea-netx
# Java 8 (Debian 11). Debian 12+ often needs Temurin 8 from Adoptium.
sudo apt install openjdk-8-jre || true
chmod +x start.sh
./start.sh
```

You still need **Python 3.10+** and a Java 8 / Web Start stack. The script creates a venv and starts the GUI.

## Install from git

Windows:

```powershell
git clone https://github.com/XRX265hun/bmc-jconsole.git
cd bmc-jconsole
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bmc_jconsole
```

Debian:

```bash
git clone https://github.com/XRX265hun/bmc-jconsole.git
cd bmc-jconsole
sudo apt install python3 python3-venv python3-tk python3-pip icedtea-netx xdotool xclip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m bmc_jconsole
```

Or: `python run.py` / `./start.sh`

## Use

1. **Settings** — point at `javaws` if it is not auto-detected.
2. **Add** a host — address, username, password, vendor (or Auto-detect).
3. **Connect** — fetches a session viewer and starts Java.
4. **Console paste** — Java KVMs ignore Ctrl+V. Use **Console paste** (types after a 3-second countdown) or **Ctrl+Alt+V** while the Java window is focused. Set **Paste keyboard** to the same language the Java console is using (US for most BIOS/Linux, Hungarian if the guest/iLO keyboard is HU).

You can also **Launch local JNLP** if you already downloaded a viewer file from the BMC page. Those files expire quickly; connect from this app when possible so a new one is fetched.

### Vendors

| Vendor | What it fetches |
| --- | --- |
| Fujitsu iRMC S2–S4 | Digest auth → `/avr.jnlp` |
| Fujitsu iRMC S5 | Redfish session → `/avr.jnlp` |
| Dell iDRAC 6/7/8 | Web login → `viewer.jnlp` |
| HPE iLO 3/4 | JSON login → Java IRC applet or JNLP |
| SuperMicro | ATEN `/cgi/login.cgi` or AMI MegaRAC session → iKVM JNLP |
| Lenovo IMM | Web login → viewer JNLP |
| Generic / local | Your URL or a `.jnlp` file on disk |

If a box has been switched to **HTML5 only**, there is no Java console to launch. Use the BMC web UI for those.

## Data

Hosts and settings are stored in `%APPDATA%\bmc-jconsole\state.json` on Windows, or `~/.config/bmc-jconsole/state.json` elsewhere. Passwords are saved there unless you turn that off in Settings. This is a lab convenience tool, not a hardened password vault.

## Security

Use this only against BMCs you administer. The helper accepts old TLS and self-signed certificates because those boxes often cannot do anything else. Treat saved passwords as plaintext on disk.

## Notes

- JNLP tokens are short-lived. Connect immediately; do not reuse an old cached file.
- Older viewers often need TLS 1.0/1.1 and a Java exception-site entry for the BMC URL. OpenWebStart / a dedicated Java 8 install is the usual fix.
- Newer iRMC S5/S6, iDRAC 9, iLO 5, and recent SuperMicro firmware prefer HTML5. This app targets the Java generation.

## License

[MIT](LICENSE)
