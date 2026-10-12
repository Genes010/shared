"""Admin-acties via UAC-elevatie, alleen wanneer nodig.

De app zelf draait als normale gebruiker. Voor een systeemwijziging schrijven
we een tijdelijk .ps1-script, starten we powershell.exe met het ``runas``-verb
(UAC-prompt) en lezen we daarna de uitvoer uit een tijdelijk bestand terug.
Meerdere wijzigingen bundel je in één script, dan krijg je maar één prompt.
"""

from __future__ import annotations

import ctypes
import os
import tempfile
import uuid

from .runner import IS_WINDOWS, PS_PREAMBLE, CommandResult, Runner

ERROR_CANCELLED = 1223
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_HIDE = 0
WAIT_TIMEOUT = 0x00000102


def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


if IS_WINDOWS:
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    _shell32.ShellExecuteExW.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


def _wrap_script(script: str, out_file: str) -> str:
    """Script dat alle uitvoer naar out_file schrijft en fouten als exitcode 1 meldt."""
    out_q = "'" + out_file.replace("'", "''") + "'"
    return (
        PS_PREAMBLE
        + "$ErrorActionPreference = 'Stop'\n"
        + "$code = 0\n"
        + "$log = & {\n"
        + "  try {\n"
        + script.strip() + "\n"
        + "  } catch {\n"
        + "    \"FOUT: $($_.Exception.Message)\"\n"
        + "    \"FOUT-ID: $($_.FullyQualifiedErrorId)\"\n"
        + "    $script:code = 1\n"
        + "  }\n"
        + "} *>&1 | Out-String -Width 200\n"
        + f"[IO.File]::WriteAllText({out_q}, $log, (New-Object System.Text.UTF8Encoding $false))\n"
        + "exit $code\n"
    )


def run_elevated(runner: Runner, script: str, *, description: str = "", timeout: float = 300) -> CommandResult:
    """Voer een PowerShell-script uit met adminrechten (UAC-prompt indien nodig)."""
    display = "ADMIN PS> " + script.strip().replace("\n", "\n          ")
    runner.log("cmd", display)
    if description:
        runner.log("info", description)

    if not IS_WINDOWS:
        res = CommandResult(display, 127, "", "Niet beschikbaar: SMB Connect werkt alleen op Windows.")
        runner.log("err", res.stderr)
        return res

    if is_admin():
        # Al admin (bijv. app als admin gestart): geen extra prompt nodig.
        res = runner.powershell("$ErrorActionPreference = 'Stop'\n" + script, timeout=timeout, quiet=True)
        if res.output:
            runner.log("out" if res.ok else "err", res.output)
        return CommandResult(display, res.returncode, res.stdout, res.stderr)

    tmp = tempfile.gettempdir()
    token = uuid.uuid4().hex
    ps_file = os.path.join(tmp, f"smbconnect_{token}.ps1")
    out_file = os.path.join(tmp, f"smbconnect_{token}.out")
    try:
        with open(ps_file, "w", encoding="utf-8-sig") as fh:
            fh.write(_wrap_script(script, out_file))

        params = f'-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps_file}"'
        info = SHELLEXECUTEINFOW()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
        info.lpVerb = "runas"
        info.lpFile = "powershell.exe"
        info.lpParameters = params
        info.nShow = SW_HIDE

        if not _shell32.ShellExecuteExW(ctypes.byref(info)):
            err = ctypes.get_last_error()
            msg = ("UAC-prompt geannuleerd, er is niets gewijzigd." if err == ERROR_CANCELLED
                   else f"Kon admin-proces niet starten (fout {err}).")
            runner.log("err", msg)
            return CommandResult(display, ERROR_CANCELLED if err == ERROR_CANCELLED else -1, "", msg)

        try:
            wait = _kernel32.WaitForSingleObject(info.hProcess, int(timeout * 1000))
            if wait == WAIT_TIMEOUT:
                msg = f"Admin-actie duurde langer dan {timeout:.0f} seconden."
                runner.log("err", msg)
                return CommandResult(display, -1, "", msg)
            code = wintypes.DWORD()
            _kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        finally:
            _kernel32.CloseHandle(info.hProcess)

        output = ""
        if os.path.exists(out_file):
            with open(out_file, encoding="utf-8", errors="replace") as fh:
                output = fh.read().strip()
        rc = int(code.value)
        if output:
            runner.log("out" if rc == 0 else "err", output)
        if rc != 0:
            runner.log("info", f"(exitcode {rc})")
        return CommandResult(display, rc, output if rc == 0 else "", "" if rc == 0 else output)
    finally:
        for path in (ps_file, out_file):
            try:
                os.remove(path)
            except OSError:
                pass
