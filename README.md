# bmc-jconsole

Desktop helper for **Java (non-HTML5)** server consoles: Fujitsu iRMC AVR, Dell iDRAC, HPE iLO Java IRC, SuperMicro iKVM, and Lenovo IMM.

It logs into the BMC, fetches a fresh viewer (`.jnlp` or the iLO 3 applet), and launches it so you do not have to click through the web UI every time.

This project is open source under the [MIT License](LICENSE). It is not affiliated with Hewlett Packard, Dell, Fujitsu, Super Micro, or Lenovo.

**This is vibe-coded.** It was written with [Cursor](https://cursor.com) as a pair programmer (yes, the `Cursor` co-author on commits is that). Treat it as a lab helper, not a vendor product. Live testing so far is mainly **HP iLO 3**; other BMC paths are included because those Java consoles still exist, not because every one was proven here. If something is wrong, open an issue or a PR — that is more useful than being angry that an AI helped write it.

## Requirements

- Python 3.10+
- **Java 8 with Web Start** (`javaws.exe`) or [OpenWebStart](https://openwebstart.com/)
- Network reachability to the BMC (self-signed TLS is accepted by default)

Modern Oracle Java 11+ does **not** include Web Start. Use an 8u JRE, or OpenWebStart.

Old BMCs (iLO 3, iRMC S2–S4, iDRAC 6, etc.) often only speak **TLS 1.0/1.1** with weak DHE ciphers. This app uses a legacy TLS client for that. iLO 3 Java IRC is an **applet** (`intgapp*.jar`), not a `.jnlp` download — the app hosts that applet after login.

## Install

```powershell
git clone https://github.com/XRX265hun/bmc-jconsole.git
cd bmc-jconsole
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bmc_jconsole
```

Or: `python run.py`

## Use

1. **Settings** — point at `javaws` if it is not auto-detected.
2. **Add** a host — address, username, password, vendor (or Auto-detect).
3. **Connect** — fetches a session viewer and starts Java.

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
