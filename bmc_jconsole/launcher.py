from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

from bmc_jconsole.store import cache_dir, data_dir


class LaunchError(RuntimeError):
    pass


def _windows_javaws_candidates() -> list[str]:
    roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    patterns = [
        r"Java\jre*\bin\javaws.exe",
        r"Java\jdk1.8*\bin\javaws.exe",
        r"Java\jdk-1.8*\bin\javaws.exe",
        r"OpenWebStart\javaws.exe",
        r"AdoptOpenJDK\*\bin\javaws.exe",
        r"Eclipse Adoptium\*\bin\javaws.exe",
    ]
    found: list[str] = []
    for root in roots:
        if not root:
            continue
        for pattern in patterns:
            found.extend(glob.glob(str(Path(root) / pattern)))
    icedtea = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "icedtea-web" / "bin" / "javaws.exe"
    if icedtea.exists():
        found.append(str(icedtea))
    return found


def _linux_javaws_candidates() -> list[str]:
    found: list[str] = []
    which = shutil.which("javaws") or shutil.which("itweb-javaws")
    if which:
        found.append(which)
    for path in (
        "/usr/share/icedtea-web/bin/javaws",
        "/usr/lib/icedtea-web/bin/javaws",
        "/usr/bin/javaws",
        str(Path.home() / ".local/share/icedtea-web/bin/javaws"),
    ):
        if Path(path).is_file():
            found.append(path)
    for path in glob.glob(str(Path.home() / ".config/icedtea-web/*/javaws")):
        found.append(path)
    for root in ("/opt/OpenWebStart", str(Path.home() / ".local/share/OpenWebStart")):
        found.extend(glob.glob(str(Path(root) / "javaws")))
        found.extend(glob.glob(str(Path(root) / "bin/javaws")))
    return found


def _linux_java8_candidates() -> list[Path]:
    patterns = [
        "/usr/lib/jvm/java-8-openjdk-*/bin/java",
        "/usr/lib/jvm/java-8-openjdk/bin/java",
        "/usr/lib/jvm/java-1.8.*/bin/java",
        "/usr/lib/jvm/zulu-8*/bin/java",
        "/usr/lib/jvm/zulu8*/bin/java",
        "/usr/lib/jvm/temurin-8*/bin/java",
        "/usr/lib/jvm/adoptopenjdk-8*/bin/java",
        "/usr/lib/jvm/jdk-8*/bin/java",
        "/usr/lib/jvm/jre-8*/bin/java",
        str(Path.home() / ".sdkman/candidates/java/8*/bin/java"),
    ]
    found: list[Path] = []
    for pattern in patterns:
        found.extend(Path(p) for p in glob.glob(pattern))
    return found


def find_javaws(configured: str = "") -> str:
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        raise LaunchError(f"Configured javaws path does not exist: {configured}")

    env = os.environ.get("JAVAWS") or os.environ.get("JAVAWS_PATH")
    if env and Path(env).is_file():
        return env

    which = shutil.which("javaws") or shutil.which("javaws.exe")
    if which:
        return which

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        for name in ("javaws.exe", "javaws"):
            candidate = Path(java_home) / "bin" / name
            if candidate.is_file():
                return str(candidate)

    if os.name == "nt":
        matches = sorted(_windows_javaws_candidates(), reverse=True)
        if matches:
            return matches[0]
    else:
        matches = _linux_javaws_candidates()
        if matches:
            return matches[0]

    raise LaunchError(
        "Could not find javaws. Install Java 8 with Web Start (Windows) or "
        "icedtea-netx / OpenWebStart (Debian: sudo apt install icedtea-netx), "
        "then set the path in Settings."
    )


def looks_like_jnlp(text: str) -> bool:
    sample = text.lstrip()[:4000].lower()
    return "<jnlp" in sample


def launch_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)[:60]
    return cleaned or "console"


def _is_java8(path: Path) -> bool:
    try:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        text = (result.stderr or "") + (result.stdout or "")
        return "1.8." in text or 'version "8' in text
    except (OSError, subprocess.SubprocessError):
        return False


def find_java8(configured_javaws: str = "") -> str:
    candidates: list[Path] = []
    try:
        javaws = Path(find_javaws(configured_javaws))
        candidates.append(javaws.with_name("java.exe" if os.name == "nt" else "java"))
    except LaunchError:
        pass
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    which = shutil.which("java")
    if which:
        candidates.append(Path(which))
    if os.name == "nt":
        for root in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            candidates.extend(Path(p) for p in glob.glob(str(Path(root) / r"Java\jre1.8*\bin\java.exe")))
            candidates.extend(Path(p) for p in glob.glob(str(Path(root) / r"Java\jdk1.8*\bin\java.exe")))
    else:
        candidates.extend(_linux_java8_candidates())
    for path in candidates:
        if path.is_file() and _is_java8(path):
            return str(path)
    raise LaunchError(
        "Could not find Java 8 (needed for iLO 3 applet). "
        "On Debian 11: sudo apt install openjdk-8-jre. "
        "On Debian 12+: install Temurin 8, or set JAVA_HOME to a Java 8 JRE."
    )


def launcher_jar() -> Path:
    path = Path(__file__).resolve().parent.parent / "java" / "ilo-applet-launcher.jar"
    if not path.is_file():
        raise LaunchError(f"Missing applet launcher: {path}")
    return path


_LOG_HANDLES: list[object] = []


def launch_ilo_applet(plan: dict, javaws_configured: str = "") -> subprocess.Popen[bytes]:
    from bmc_jconsole.legacy_ssl import legacy_security_file

    java = find_java8(javaws_configured)
    jar = Path(plan["jar"])
    if not jar.is_file():
        raise LaunchError(f"iLO IRC jar missing: {jar}")
    security = legacy_security_file()
    classpath = os.pathsep.join((str(launcher_jar()), str(jar)))
    cmd = [
        java,
        f"-Djava.security.properties={security}",
        "-Dhttps.protocols=TLSv1,TLSv1.1,TLSv1.2",
        "-Dsun.java2d.noddraw=true",
        "-Dsun.java2d.d3d=false",
        "-Dsun.java2d.opengl=false",
        "-Dsun.java2d.dpiaware=false",
        "-Dsun.java2d.uiScale=1",
        "-Duser.language=en",
        "-Duser.country=US",
        "-cp",
        classpath,
        "IloAppletLauncher",
        plan["main_class"],
        plan["codebase"],
        plan["documentbase"],
    ]
    for key, value in (plan.get("params") or {}).items():
        cmd.append(f"{key}={value}")
    log_path = data_dir() / "applet.log"
    handle = log_path.open("ab")
    _LOG_HANDLES.append(handle)
    handle.write(f"\n--- launch {java} ---\n".encode("utf-8"))
    handle.flush()
    try:
        return subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT)
    except OSError as exc:
        handle.close()
        raise LaunchError(f"Failed to start iLO applet: {exc}") from exc


def write_jnlp(text: str, stem: str) -> Path:
    path = cache_dir() / f"{launch_stem(stem)}.jnlp"
    path.write_text(text, encoding="utf-8")
    return path


def launch_jnlp(jnlp_path: Path, javaws_path: str) -> subprocess.Popen[bytes]:
    if not jnlp_path.is_file():
        raise LaunchError(f"JNLP file not found: {jnlp_path}")
    try:
        return subprocess.Popen(
            [javaws_path, str(jnlp_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise LaunchError(f"Failed to start javaws: {exc}") from exc
