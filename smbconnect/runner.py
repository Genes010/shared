"""Uitvoeren van externe commando's (PowerShell, net, cmdkey) met logging.

Alle commando's lopen via één Runner zodat elk commando en de uitvoer in het
log-venster terechtkomen. Wachtwoorden worden nooit gelogd: geef ze mee via
``secrets`` (worden gemaskeerd) of liever via ``env`` (komen dan niet eens op
de commandoregel terecht).
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

IS_WINDOWS = os.name == "nt"

# Verbergt het consolevenster van child-processen in de --windowed .exe.
CREATE_NO_WINDOW = 0x08000000

# Vast voorvoegsel voor elk PowerShell-script: UTF-8 uitvoer, geen
# voortgangsbalken (die komen anders als CLIXML op stderr terecht).
PS_PREAMBLE = (
    "$ProgressPreference = 'SilentlyContinue'\n"
    "try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}\n"
)

LogFunc = Callable[[str, str], None]  # (soort, tekst) met soort in cmd/out/err/info


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    data: object = field(default=None)  # geparste JSON bij ps_json()

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return "\n".join(p for p in (self.stdout.strip(), self.stderr.strip()) if p)


def ps_quote(value: str) -> str:
    """Zet een waarde veilig tussen enkele quotes voor PowerShell."""
    return "'" + str(value).replace("'", "''") + "'"


def encode_ps(script: str) -> str:
    """Base64 UTF-16LE voor ``powershell -EncodedCommand``."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


_CLIXML_STRING = re.compile(r'<S S="(?:Error|Warning)">(.*?)</S>', re.S)


def clean_clixml(text: str) -> str:
    """Maak CLIXML-foutuitvoer van powershell.exe weer leesbaar."""
    if "#< CLIXML" not in text:
        return text
    parts = _CLIXML_STRING.findall(text)
    joined = "".join(parts)
    joined = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), joined)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        joined = joined.replace(a, b)
    return joined.strip()


def parse_json_output(stdout: str):
    """Haal de JSON uit PowerShell-uitvoer (laatste JSON-regel als er meer staat)."""
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line[:1] in "{[":
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def as_list(data) -> list:
    """ConvertTo-Json geeft bij één element een object i.p.v. een lijst."""
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


def _decode(raw: bytes, console: bool) -> str:
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    if console and IS_WINDOWS:
        # net.exe / cmdkey.exe schrijven in de OEM-codepage (bijv. cp850).
        try:
            return raw.decode("oem", errors="replace")
        except LookupError:
            pass
    return raw.decode("utf-8", errors="replace")


class Runner:
    def __init__(self, log: LogFunc | None = None):
        self._log = log or (lambda kind, text: None)
        self._lock = threading.Lock()

    def log(self, kind: str, text: str) -> None:
        self._log(kind, text)

    @staticmethod
    def _mask(text: str, secrets: Iterable[str]) -> str:
        for s in secrets:
            if s:
                text = text.replace(s, "********")
        return text

    def run(
        self,
        args: list[str],
        *,
        timeout: float = 60,
        display: str | None = None,
        secrets: Iterable[str] = (),
        env: Mapping[str, str] | None = None,
        console_encoding: bool = True,
        quiet: bool = False,
    ) -> CommandResult:
        """Voer een programma uit en log commando + uitvoer."""
        secrets = [s for s in secrets if s]
        shown = self._mask(display or subprocess.list2cmdline(args), secrets)
        if not quiet:
            self.log("cmd", shown)

        if not IS_WINDOWS:
            result = CommandResult(shown, 127, "", "Niet beschikbaar: SMB Connect werkt alleen op Windows.")
            if not quiet:
                self.log("err", result.stderr)
            return result

        full_env = None
        if env:
            full_env = dict(os.environ)
            full_env.update(env)
        try:
            proc = subprocess.run(
                args,
                stdin=subprocess.DEVNULL,  # windowed .exe heeft geen stdin
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=full_env,
                creationflags=CREATE_NO_WINDOW,
            )
            result = CommandResult(
                shown,
                proc.returncode,
                _decode(proc.stdout, console_encoding),
                clean_clixml(_decode(proc.stderr, console_encoding)),
            )
        except subprocess.TimeoutExpired:
            result = CommandResult(shown, -1, "", f"Time-out na {timeout:.0f} seconden.")
        except OSError as exc:
            result = CommandResult(shown, -1, "", f"Kon commando niet starten: {exc}")

        if not quiet:
            if result.stdout.strip():
                self.log("out", self._mask(result.stdout.rstrip(), secrets))
            if result.stderr.strip():
                self.log("err", self._mask(result.stderr.rstrip(), secrets))
            if result.returncode != 0:
                self.log("info", f"(exitcode {result.returncode})")
        return result

    def powershell(
        self,
        script: str,
        *,
        timeout: float = 60,
        env: Mapping[str, str] | None = None,
        secrets: Iterable[str] = (),
        quiet: bool = False,
    ) -> CommandResult:
        """Voer een PowerShell-script uit (Windows PowerShell 5.1)."""
        full = PS_PREAMBLE + script
        args = [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-OutputFormat", "Text",
            "-EncodedCommand", encode_ps(full),
        ]
        # In het log tonen we het leesbare script i.p.v. de base64-blob.
        display = "PS> " + script.strip().replace("\n", "\n    ")
        return self.run(args, timeout=timeout, display=display, secrets=secrets,
                        env=env, console_encoding=False, quiet=quiet)

    def ps_json(self, script: str, **kwargs) -> CommandResult:
        """Voer een script uit waarvan de uitvoer naar JSON wordt omgezet."""
        wrapped = f"& {{\n{script.strip()}\n}} | ConvertTo-Json -Depth 5 -Compress"
        result = self.powershell(wrapped, **kwargs)
        result.data = parse_json_output(result.stdout)
        return result
