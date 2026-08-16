# bmc-jconsole

Desktop helper for **Java (non-HTML5)** server consoles: Fujitsu iRMC AVR, Dell iDRAC, HPE iLO Java IRC, SuperMicro iKVM, and Lenovo IMM.

It logs into the BMC, downloads a fresh `.jnlp`, and launches it with `javaws` so you do not have to click through the web UI every time.

## Requirements

- Python 3.10+
- **Java 8 with Web Start** (`javaws.exe`) or [OpenWebStart](https://openwebstart.com/)
- Network reachability to the BMC (self-signed TLS is accepted by default)

Modern Oracle Java 11+ does **not** include Web Start. Use an 8u JRE, or OpenWebStart.

Old BMCs (iLO 3, iRMC S2–S4, iDRAC 6, etc.) often only speak **TLS 1.0/1.1** with weak DHE ciphers. This app uses a legacy TLS client for that. iLO 3 Java IRC is an **applet** (`intgapp*.jar`), not a `.jnlp` download — the app builds a JNLP wrapper after login.

## Run

```powershell
cd $env:USERPROFILE\bmc-jconsole
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bmc_jconsole
```

Or: `python run.py`

## Use

1. **Settings** — point at `javaws` if it is not auto-detected.
2. **Add** a host — address, username, password, vendor (or Auto-detect).
3. **Connect** — fetches a session JNLP and starts the Java viewer.

You can also **Launch local JNLP** if you already downloaded a viewer file from the BMC page. Those files expire quickly; connect from this app when possible so a new one is fetched.

### Vendors

| Vendor | What it fetches |
| --- | --- |
| Fujitsu iRMC S2–S4 | Digest auth → `/avr.jnlp` |
| Fujitsu iRMC S5 | Redfish session → `/avr.jnlp` |
| Dell iDRAC 6/7/8 | Web login → `viewer.jnlp` |
| HPE iLO 3/4 | JSON login → Java IRC JNLP |
| SuperMicro | ATEN `/cgi/login.cgi` or AMI MegaRAC session → iKVM JNLP |
| Lenovo IMM | Web login → viewer JNLP |
| Generic / local | Your URL or a `.jnlp` file on disk |

If a box has been switched to **HTML5 only**, there is no Java console to launch. Use the BMC web UI for those.

## Data

Hosts and settings are stored in `%APPDATA%\bmc-jconsole\state.json`. Passwords are saved there unless you turn that off in Settings. This is a lab convenience tool, not a hardened password vault.

## Notes

- JNLP tokens are short-lived. Connect immediately; do not reuse an old cached file.
- Older viewers often need TLS 1.0/1.1 and a Java exception-site entry for the BMC URL. OpenWebStart / a dedicated Java 8 install is the usual fix.
- Newer iRMC S5/S6, iDRAC 9, iLO 5, and recent SuperMicro firmware prefer HTML5. This app targets the Java generation.
