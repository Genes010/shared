"""Stap-voor-stap diagnose van een SMB-verbinding naar één server.

Elke stap levert een CheckResult op met een status (groen/oranje/rood),
uitleg en een voorgestelde oplossing. De logica staat los van de UI zodat
hij met een nep-runner te testen is.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Callable

from .errors import explain, extract_error_code
from .runner import Runner, as_list, ps_quote

OK, WARN, FAIL, INFO, SKIP = "ok", "warn", "fail", "info", "skip"

STEPS: list[tuple[str, str]] = [
    ("resolve", "Naamresolutie"),
    ("ping", "Ping / bereikbaarheid"),
    ("port", "Poort 445 (SMB)"),
    ("auth", "Authenticatie"),
    ("dialect", "SMB-dialect"),
    ("account", "Accounttype"),
    ("client", "Lokale client-instellingen"),
]
STEP_TITLES = dict(STEPS)


@dataclass
class CheckResult:
    key: str
    status: str
    summary: str
    detail: str = ""
    fix: str = ""

    @property
    def title(self) -> str:
        return STEP_TITLES.get(self.key, self.key)


@dataclass
class DiagnoseParams:
    host: str
    share: str = ""
    username: str = ""
    password: str = ""          # alleen in geheugen, nooit opgeslagen
    ip_fallback: str = ""


@dataclass
class DiagnoseState:
    """Tussenresultaten die volgende stappen nodig hebben."""
    target: str = ""             # adres waarmee we verder testen (host of IP)
    ips: list[str] = field(default_factory=list)
    reachable: bool = False
    port_open: bool = False
    auth_ok: bool = False
    error_code: int | None = None
    connection: dict | None = None


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
        return True
    except ValueError:
        return False


def normalize_host(value: str) -> str:
    """Accepteer ook '\\\\server\\share' of 'server\\share' en geef alleen de server terug."""
    v = value.strip().lstrip("\\/")
    return re.split(r"[\\/]", v, maxsplit=1)[0]


# --------------------------------------------------------------------------
# Losse stappen
# --------------------------------------------------------------------------

def check_resolution(runner: Runner, p: DiagnoseParams, st: DiagnoseState) -> CheckResult:
    host = p.host
    if is_ip(host):
        st.target = host
        st.ips = [host]
        return CheckResult("resolve", OK, f"{host} is een IP-adres, naamresolutie niet nodig.",
                           "Werken op IP is het meest betrouwbaar als de naam niet gevonden wordt.")

    script = f"""
try {{
  $a = [System.Net.Dns]::GetHostAddresses({ps_quote(host)}) | ForEach-Object {{ $_.IPAddressToString }}
  [pscustomobject]@{{ ok = $true; ips = @($a) }}
}} catch {{
  [pscustomobject]@{{ ok = $false; error = $_.Exception.InnerException.Message }}
}}"""
    res = runner.ps_json(script, timeout=30)
    data = res.data if isinstance(res.data, dict) else {}
    ips = [str(i) for i in as_list(data.get("ips"))]

    if data.get("ok") and ips:
        v4 = [i for i in ips if ":" not in i]
        st.ips = ips
        st.target = host
        detail = f"{host} → {', '.join(ips)}"
        if p.ip_fallback and p.ip_fallback not in ips:
            return CheckResult(
                "resolve", WARN, f"{host} gevonden, maar met een ander IP dan opgeslagen ({p.ip_fallback}).",
                detail,
                "Het IP van de server is mogelijk veranderd (DHCP). Pas het IP in het profiel aan of geef "
                "de server een vast IP / DHCP-reservering in je router.")
        if v4 and all(i.startswith("169.254.") for i in v4):
            return CheckResult("resolve", WARN, f"{host} heeft alleen een APIPA-adres (169.254.x.x).", detail,
                               "De server heeft geen IP van de router gekregen. Controleer de netwerkkabel/wifi.")
        return CheckResult("resolve", OK, f"{host} gevonden: {', '.join(v4 or ips)}", detail)

    err = data.get("error") or res.output or "onbekende fout"
    fix = ("Windows kan de computernaam niet omzetten naar een IP-adres. Oplossingen: "
           "1) gebruik het IP-adres van de server; "
           "2) zet op de server 'Netwerkdetectie' aan en het netwerkprofiel op Privé "
           "(tab 'Deze machine als server'); "
           "3) controleer of beide machines in hetzelfde netwerk/subnet zitten.")
    if p.ip_fallback:
        st.target = p.ip_fallback
        st.ips = [p.ip_fallback]
        return CheckResult("resolve", WARN,
                           f"{host} niet gevonden, verder met opgeslagen IP {p.ip_fallback}.",
                           f"Fout: {err}", fix)
    st.target = ""
    return CheckResult("resolve", FAIL, f"{host} kan niet worden gevonden.", f"Fout: {err}", fix)


def check_reachability(runner: Runner, st: DiagnoseState) -> tuple[CheckResult, CheckResult]:
    """Ping en poort 445 in één Test-NetConnection-aanroep."""
    if not st.target:
        skip = "Overgeslagen: geen adres om te testen."
        return CheckResult("ping", SKIP, skip), CheckResult("port", SKIP, skip)

    script = f"""
$r = Test-NetConnection -ComputerName {ps_quote(st.target)} -Port 445 -WarningAction SilentlyContinue
[pscustomobject]@{{
  tcp = [bool]$r.TcpTestSucceeded
  ping = [bool]$r.PingSucceeded
  remote = "$($r.RemoteAddress)"
  source = "$($r.SourceAddress.IPAddress)"
  iface = "$($r.InterfaceAlias)"
}}"""
    res = runner.ps_json(script, timeout=90)
    data = res.data if isinstance(res.data, dict) else {}
    if not data:
        msg = "Test-NetConnection gaf geen bruikbaar resultaat."
        return (CheckResult("ping", FAIL, msg, res.output),
                CheckResult("port", FAIL, msg, res.output))

    ping_ok = bool(data.get("ping"))
    tcp_ok = bool(data.get("tcp"))
    st.reachable = ping_ok or tcp_ok
    st.port_open = tcp_ok
    via = f"Via {data.get('iface') or '?'} ({data.get('source') or '?'}) naar {data.get('remote') or st.target}."

    if ping_ok:
        ping = CheckResult("ping", OK, f"{st.target} antwoordt op ping.", via)
    elif tcp_ok:
        ping = CheckResult("ping", WARN, "Geen antwoord op ping, maar SMB werkt wel.", via,
                           "De Windows-firewall op de server blokkeert ping (ICMP). Dat is standaard en "
                           "geen probleem voor gedeelde mappen.")
    else:
        ping = CheckResult("ping", FAIL, f"{st.target} reageert niet.", via,
                           "Staat de server aan en zit hij in hetzelfde netwerk? Klopt het IP-adres? "
                           "Let op: Windows blokkeert ping standaard, dus kijk vooral naar de poort-test.")

    if tcp_ok:
        port = CheckResult("port", OK, "Poort 445 is open: de server accepteert SMB-verbindingen.", via)
    else:
        port = CheckResult(
            "port", FAIL, "Poort 445 is dicht of gefilterd.", via,
            "Op de server: zet het netwerkprofiel op Privé, schakel de firewallregel 'Bestands- en "
            "printerdeling' in en controleer of de dienst 'Server' (LanmanServer) draait. Dit kan met "
            "één klik in tab 'Deze machine als server' op de server zelf. Een externe firewall/antivirus "
            "of een gastnetwerk (client-isolatie) kan ook blokkeren.")
    return ping, port


def _auth_script(target: str, share: str) -> str:
    return f"""
$target = {ps_quote(target)}
$share = {ps_quote(share)}
$path = "\\\\$target\\$share"
$res = [ordered]@{{ ok = $false; existing = $false; created = $false; error = $null; errorId = $null; hresult = $null; conn = $null }}
try {{
  $map = @(Get-SmbMapping -RemotePath $path -ErrorAction SilentlyContinue)
  $conn = @(Get-SmbConnection -ServerName $target -ErrorAction SilentlyContinue | Where-Object {{ $_.ShareName -eq $share }})
  if ($map.Count -gt 0 -or $conn.Count -gt 0) {{
    $res.existing = $true; $res.ok = $true
  }} else {{
    $p = @{{ RemotePath = $path; ErrorAction = 'Stop' }}
    if ($env:SMBC_PASS) {{ $p.UserName = $env:SMBC_USER; $p.Password = $env:SMBC_PASS }}
    New-SmbMapping @p | Out-Null
    $res.created = $true; $res.ok = $true
  }}
  $c = Get-SmbConnection -ServerName $target -ErrorAction SilentlyContinue | Where-Object {{ $_.ShareName -eq $share }} | Select-Object -First 1
  if ($c) {{
    $res.conn = [pscustomobject]@{{ dialect = "$($c.Dialect)"; user = "$($c.UserName)"; credential = "$($c.Credential)"; signed = $c.Signed; encrypted = $c.Encrypted }}
  }}
  if ($res.created) {{ Remove-SmbMapping -RemotePath $path -Force -ErrorAction SilentlyContinue }}
}} catch {{
  $res.error = $_.Exception.Message
  $res.errorId = "$($_.FullyQualifiedErrorId)"
  $res.hresult = $_.Exception.HResult
}}
[pscustomobject]$res"""


def check_auth(runner: Runner, p: DiagnoseParams, st: DiagnoseState) -> CheckResult:
    if not st.port_open:
        return CheckResult("auth", SKIP, "Overgeslagen: poort 445 is niet bereikbaar.")

    share = p.share.strip("\\/") or "IPC$"
    env = {"SMBC_USER": p.username or "", "SMBC_PASS": p.password or ""}
    res = runner.ps_json(_auth_script(st.target, share), timeout=60, env=env, secrets=[p.password])
    data = res.data if isinstance(res.data, dict) else {}
    path = f"\\\\{st.target}\\{share}"
    how = ("met het opgegeven wachtwoord" if p.password
           else "met opgeslagen inloggegevens of je eigen Windows-aanmelding")

    if data.get("ok"):
        st.auth_ok = True
        st.connection = data.get("conn") if isinstance(data.get("conn"), dict) else None
        user = (st.connection or {}).get("credential") or (st.connection or {}).get("user") or ""
        detail = f"Getest op {path} {how}." + (f" Aangemeld als: {user}." if user else "")
        if data.get("existing"):
            return CheckResult("auth", OK, "Er is al een werkende verbinding met deze share.", detail)
        return CheckResult("auth", OK, "Aanmelden gelukt.", detail + " De testverbinding is weer verbroken.")

    err_text = " ".join(str(x) for x in (data.get("error"), data.get("errorId")) if x) or res.output
    code = extract_error_code(err_text)
    hres = data.get("hresult")
    if code is None and isinstance(hres, int) and (hres & 0xFFFF0000) == 0x80070000:
        code = hres & 0xFFFF  # HRESULT_FROM_WIN32 (signed int32, maar & werkt op beide)
    st.error_code = code
    info = explain(code)
    detail = f"Getest op {path} {how}.\nMelding: {err_text.strip() or 'geen'}"
    if info:
        return CheckResult("auth", FAIL, f"Fout {code}: {info.title}.", detail + f"\n\n{info.explanation}", info.fix)
    if code is not None:
        return CheckResult("auth", FAIL, f"Aanmelden mislukt (fout {code}).", detail,
                           "Zoek de foutcode op of bekijk het log voor de volledige melding.")
    return CheckResult("auth", FAIL, "Aanmelden mislukt.", detail,
                       "Bekijk het log onderin voor de volledige melding.")


def check_dialect(st: DiagnoseState) -> CheckResult:
    if not st.auth_ok:
        return CheckResult("dialect", SKIP, "Overgeslagen: er is geen verbinding.")
    conn = st.connection or {}
    dialect = str(conn.get("dialect") or "").strip()
    extra = []
    if conn.get("signed") is not None:
        extra.append(f"Signing: {'ja' if conn.get('signed') else 'nee'}")
    if conn.get("encrypted") is not None:
        extra.append(f"Versleuteld: {'ja' if conn.get('encrypted') else 'nee'}")
    detail = ", ".join(extra)
    if not dialect:
        return CheckResult("dialect", INFO, "Dialect kon niet worden uitgelezen.", detail,
                           "Get-SmbConnection gaf geen gegevens terug. Dat is geen probleem voor het koppelen.")
    if dialect.startswith("3"):
        return CheckResult("dialect", OK, f"SMB {dialect}: modern en veilig.", detail)
    if dialect.startswith("2"):
        return CheckResult("dialect", WARN, f"SMB {dialect}: werkt, maar verouderd.", detail,
                           "De server ondersteunt geen SMB 3. Dit is vaak een oudere NAS; controleer of er "
                           "een firmware-update is en zet daar de minimale SMB-versie op SMB2/3.")
    return CheckResult("dialect", FAIL, f"SMB {dialect}: onveilig en niet ondersteund door Windows 11.", detail,
                       "Zet op de server SMB2 of hoger aan. SMB1 wordt door Windows 11 niet meer ondersteund.")


def check_account(p: DiagnoseParams) -> CheckResult:
    user = p.username.strip()
    host_label = p.host.split(".")[0].lower()
    if not user:
        return CheckResult("account", INFO, "Geen gebruikersnaam opgegeven.",
                           "Windows gebruikt dan opgeslagen inloggegevens (Credential Manager) of je eigen "
                           "Windows-aanmelding. Dat werkt alleen als op de server hetzelfde account met "
                           "hetzelfde wachtwoord bestaat.")
    low = user.lower()
    if low.startswith("microsoftaccount\\") or "@" in low:
        fix = ("Gebruik het wachtwoord van het Microsoft-account, niet de PIN. Log op de server minstens "
               "één keer in met het wachtwoord (niet met PIN/Windows Hello), anders kent de server het "
               "wachtwoord nog niet. Staat op de server 'Voor betere beveiliging alleen Windows Hello-"
               "aanmelding toestaan' aan? Zet dat dan uit (Instellingen > Accounts > Aanmeldingsopties). "
               "Alternatief: maak op de server een apart lokaal account voor delen.")
        if not low.startswith("microsoftaccount\\"):
            fix = f"Gebruik de vorm MicrosoftAccount\\{user}. " + fix
        return CheckResult("account", WARN, "Microsoft-account: SMB vereist het echte wachtwoord, geen PIN.",
                           "Bij Microsoft-accounts met alleen PIN/Windows Hello faalt SMB met fout 1326.", fix)
    if "\\" in user:
        prefix = user.split("\\", 1)[0].lower()
        if prefix not in (".", host_label, p.ip_fallback.lower(), p.host.lower()) and not is_ip(p.host):
            return CheckResult("account", INFO, f"Lokaal/domein-account: {user}",
                               f"Het voorvoegsel '{user.split(chr(92))[0]}' is niet gelijk aan de servernaam "
                               f"'{p.host}'. Bij een lokaal account op de server hoort hier de computernaam "
                               "van de server te staan.")
        return CheckResult("account", OK, f"Lokaal account op de server: {user}")
    return CheckResult("account", INFO, f"Gebruikersnaam zonder servernaam: {user}",
                       "Dat werkt meestal, maar SERVER\\gebruiker is eenduidiger.",
                       f"Gebruik bij voorkeur {p.host.split('.')[0].upper()}\\{user}.")


CLIENT_SCRIPT = r"""
$c = Get-SmbClientConfiguration
$pol = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\LanmanWorkstation' -ErrorAction SilentlyContinue
$pl = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device' -ErrorAction SilentlyContinue
[pscustomobject]@{
  RequireSecuritySignature = $c.RequireSecuritySignature
  EnableSecuritySignature = $c.EnableSecuritySignature
  EnableInsecureGuestLogons = $c.EnableInsecureGuestLogons
  PolicyAllowInsecureGuestAuth = $pol.AllowInsecureGuestAuth
  PasswordLess = $pl.DevicePasswordLessBuildVersion
}"""


def check_client(runner: Runner, st: DiagnoseState) -> CheckResult:
    res = runner.ps_json(CLIENT_SCRIPT, timeout=30)
    data = res.data if isinstance(res.data, dict) else {}
    if not data:
        return CheckResult("client", INFO, "Client-instellingen konden niet worden uitgelezen.", res.output)

    req_sign = data.get("RequireSecuritySignature")
    guest = data.get("EnableInsecureGuestLogons")
    pol_guest = data.get("PolicyAllowInsecureGuestAuth")
    lines = [
        f"RequireSecuritySignature: {req_sign}  (signing verplicht)",
        f"EnableSecuritySignature: {data.get('EnableSecuritySignature')}",
        f"EnableInsecureGuestLogons: {guest}  (gasttoegang)",
        f"Beleid AllowInsecureGuestAuth: {'niet ingesteld' if pol_guest is None else pol_guest}",
    ]
    if data.get("PasswordLess") == 2:
        lines.append("Deze pc: 'Alleen Windows Hello-aanmelding' staat aan (relevant als deze pc server is).")
    detail = "\n".join(lines)

    if st.error_code == 1272:
        return CheckResult("client", WARN, "Gasttoegang is geblokkeerd op deze pc.", detail,
                           "De server vraagt om gasttoegang. Liever: maak op de server een account met "
                           "wachtwoord. Anders: 'Gasttoegang toestaan' onder Geavanceerd.")
    if st.error_code in (64, 59) and req_sign:
        return CheckResult("client", WARN, "Deze pc vereist SMB-signing.", detail,
                           "Windows 11 24H2 vereist standaard signing. Oudere NAS'en ondersteunen dat soms niet: "
                           "zet signing aan op de NAS, of (minder veilig) zet de signing-vereiste uit onder "
                           "Geavanceerd.")
    summary = "Signing verplicht: " + ("ja" if req_sign else "nee") + \
              " · Gasttoegang: " + ("toegestaan" if guest else "geblokkeerd")
    return CheckResult("client", INFO, summary, detail)


# --------------------------------------------------------------------------
# Volledige diagnose
# --------------------------------------------------------------------------

def run_diagnosis(runner: Runner, p: DiagnoseParams,
                  emit: Callable[[CheckResult], None] | None = None) -> list[CheckResult]:
    emit = emit or (lambda r: None)
    p.host = normalize_host(p.host)
    st = DiagnoseState()
    results: list[CheckResult] = []

    def add(r: CheckResult) -> None:
        results.append(r)
        emit(r)

    runner.log("info", f"=== Diagnose {p.host}{(chr(92) + p.share) if p.share else ''} ===")
    add(check_resolution(runner, p, st))
    ping, port = check_reachability(runner, st)
    add(ping)
    add(port)
    add(check_auth(runner, p, st))
    add(check_dialect(st))
    add(check_account(p))
    add(check_client(runner, st))
    runner.log("info", "=== Diagnose klaar ===")
    return results


def format_report(p: DiagnoseParams, results: list[CheckResult]) -> str:
    icons = {OK: "[OK]  ", WARN: "[LET OP]", FAIL: "[FOUT]", INFO: "[INFO]", SKIP: "[--]  "}
    out = [f"SMB Connect diagnose: \\\\{p.host}\\{p.share}".rstrip("\\"), ""]
    for r in results:
        out.append(f"{icons.get(r.status, r.status)} {r.title}: {r.summary}")
        for line in r.detail.splitlines():
            out.append(f"        {line}")
        if r.fix:
            out.append(f"        Oplossing: {r.fix}")
    return "\n".join(out)
