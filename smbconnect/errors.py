"""Vertaling van Windows/SMB-foutcodes naar begrijpelijke uitleg + oplossing."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SmbError:
    code: int
    title: str
    explanation: str
    fix: str


ERRORS: dict[int, SmbError] = {e.code: e for e in [
    SmbError(
        5, "Toegang geweigerd",
        "De server kent je account, maar je hebt geen rechten op deze share of map.",
        "Geef op de server de gebruiker rechten op de share én op de map (NTFS): "
        "Eigenschappen > Delen > Geavanceerd delen > Machtigingen, en tabblad Beveiliging. "
        "Op de server kan dat ook via tab 'Deze machine als server'.",
    ),
    SmbError(
        53, "Netwerkpad niet gevonden",
        "De server is niet bereikbaar via SMB: hij staat uit, de naam klopt niet, "
        "of de firewall blokkeert 'Bestands- en printerdeling' (poort 445).",
        "Controleer de servernaam/het IP. Zet op de server het netwerkprofiel op Privé en "
        "schakel 'Bestands- en printerdeling' in (tab 'Deze machine als server').",
    ),
    SmbError(
        64, "Netwerknaam niet meer beschikbaar",
        "De verbinding is tijdens het opzetten verbroken. Vaak een SMB-signing- of "
        "versieprobleem, of de server weigert de verbinding.",
        "Controleer SMB-signing (client vereist signing, server ondersteunt het niet?) en of "
        "de server SMB2/3 ondersteunt.",
    ),
    SmbError(
        67, "Sharenaam niet gevonden",
        "De server is bereikbaar, maar een share met deze naam bestaat niet.",
        "Gebruik 'Shares ophalen' om de juiste naam te kiezen. Let op: een $ aan het eind "
        "(bijv. C$) is een verborgen admin-share.",
    ),
    SmbError(
        86, "Wachtwoord onjuist",
        "Het opgegeven wachtwoord klopt niet.",
        "Voer het wachtwoord opnieuw in. Bij een Microsoft-account: gebruik het wachtwoord "
        "van het Microsoft-account, niet de PIN.",
    ),
    SmbError(
        1203, "Geen netwerkprovider accepteert het pad",
        "Windows herkent het pad niet als SMB-pad. Meestal een typefout in de servernaam of "
        "de dienst 'Werkstation' (LanmanWorkstation) draait niet.",
        "Controleer het pad (\\\\server\\share) en of de dienst Werkstation draait.",
    ),
    SmbError(
        1219, "Meerdere verbindingen met verschillende inloggegevens",
        "Er is al een verbinding met deze server onder een andere gebruikersnaam. Windows "
        "staat maar één set inloggegevens per server toe.",
        "Ontkoppel eerst alle verbindingen met deze server (ook die zonder schijfletter, zie "
        "'net use'), of verbind via het IP-adres in plaats van de naam: Windows ziet dat als "
        "een andere server.",
    ),
    SmbError(
        1222, "Netwerk niet aanwezig",
        "Er is geen actieve netwerkverbinding, of de netwerkdienst is niet gestart.",
        "Controleer de netwerkverbinding en of de dienst Werkstation draait.",
    ),
    SmbError(
        1240, "Account niet gemachtigd vanaf dit station",
        "Het account mag niet inloggen vanaf deze computer.",
        "Controleer op de server de accountbeperkingen.",
    ),
    SmbError(
        1272, "Gasttoegang geblokkeerd",
        "De server laat alleen gasttoegang (zonder wachtwoord) toe, maar Windows 11 blokkeert "
        "onveilige gastaanmeldingen standaard. Dit is de meest voorkomende fout bij NAS'en en "
        "oudere apparaten.",
        "Beste oplossing: maak op de server een gebruiker met wachtwoord en log daarmee in. "
        "Alleen als dat niet kan: 'Gasttoegang toestaan' onder Geavanceerd (minder veilig).",
    ),
    SmbError(
        1326, "Gebruikersnaam of wachtwoord onjuist",
        "De server accepteert de combinatie van gebruikersnaam en wachtwoord niet.",
        "Gebruik de vorm SERVER\\gebruiker (lokaal account op de server) of "
        "MicrosoftAccount\\naam@outlook.com. Gebruik het echte wachtwoord, niet de PIN. "
        "Bestaat het account op de server en heeft het een wachtwoord?",
    ),
    SmbError(
        1327, "Accountbeperking",
        "Vaak: het account op de server heeft een leeg wachtwoord. Windows staat netwerk-"
        "aanmelding met een leeg wachtwoord niet toe.",
        "Geef het account op de server een wachtwoord.",
    ),
    SmbError(
        1330, "Wachtwoord verlopen",
        "Het wachtwoord van het account op de server is verlopen.",
        "Log op de server in en wijzig het wachtwoord.",
    ),
    SmbError(
        1331, "Account uitgeschakeld",
        "Het account op de server is uitgeschakeld.",
        "Schakel het account op de server in (Computerbeheer > Lokale gebruikers).",
    ),
    SmbError(
        1385, "Aanmeldingstype niet toegestaan",
        "Het account heeft geen recht om via het netwerk in te loggen ('Toegang tot deze "
        "computer vanaf het netwerk' of het staat in 'Toegang weigeren').",
        "Controleer op de server het lokaal beveiligingsbeleid voor netwerktoegang.",
    ),
    SmbError(
        1909, "Account vergrendeld",
        "Het account is vergrendeld na te veel mislukte aanmeldpogingen.",
        "Wacht tot de vergrendeling verloopt of ontgrendel het account op de server.",
    ),
    SmbError(
        2202, "Ongeldige gebruikersnaam",
        "De opgegeven gebruikersnaam heeft een ongeldige vorm.",
        "Gebruik SERVER\\gebruiker of MicrosoftAccount\\naam@outlook.com.",
    ),
    SmbError(
        1312, "Aanmeldsessie bestaat niet",
        "Windows kon geen aanmeldsessie maken, vaak bij opgeslagen inloggegevens die niet "
        "meer kloppen.",
        "Verwijder de opgeslagen inloggegevens voor deze server en probeer opnieuw.",
    ),
    SmbError(
        2242, "Wachtwoord verlopen",
        "Het wachtwoord van dit account is verlopen.",
        "Wijzig het wachtwoord op de server.",
    ),
]}

# Code-aliassen: zelfde betekenis, ander nummer.
ERRORS[1311] = SmbError(1311, "Geen aanmeldserver beschikbaar",
                        "Er is geen server beschikbaar om de aanmelding te verwerken.",
                        "Controleer de gebruikersnaam (SERVER\\gebruiker) en de netwerkverbinding.")

_CODE_PATTERNS = [
    re.compile(r"(?:system\s*error|systeemfout|windows\s+system\s+error|error\s+code|foutcode|"
               r"systemfehler)\s*:?\s*(\d{1,5})", re.I),
    re.compile(r"\b0x8007([0-9a-f]{4})\b", re.I),  # HRESULT_FROM_WIN32
]

# Herkenning op tekst als er geen code in de melding staat (Engels + Nederlands).
_TEXT_HINTS: list[tuple[int, tuple[str, ...]]] = [
    (1326, ("user name or password is incorrect", "gebruikersnaam of het wachtwoord is onjuist",
            "unknown user name or bad password")),
    (1272, ("cannot access this shared folder because your organization's security policies block "
            "unauthenticated guest access", "niet-geverifieerde gasttoegang")),
    (1219, ("multiple connections to a server or shared resource by the same user",
            "meerdere verbindingen met een server")),
    (67, ("network name cannot be found", "netwerknaam is niet gevonden", "netwerknaam kan niet")),
    (53, ("network path was not found", "netwerkpad is niet gevonden", "netwerkpad kan niet")),
    (5, ("access is denied", "toegang geweigerd", "toegang is geweigerd")),
    (1327, ("account restriction", "accountbeperking")),
    (86, ("specified network password is not correct", "opgegeven netwerkwachtwoord is onjuist")),
]


def extract_error_code(*texts: str | None) -> int | None:
    """Zoek een Windows-foutcode in (fout)uitvoer van net use / PowerShell."""
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return None
    m = _CODE_PATTERNS[0].search(blob)
    if m:
        return int(m.group(1))
    m = _CODE_PATTERNS[1].search(blob)
    if m:
        return int(m.group(1), 16)
    low = blob.lower()
    for code, hints in _TEXT_HINTS:
        if any(h in low for h in hints):
            return code
    return None


def explain(code: int | None) -> SmbError | None:
    if code is None:
        return None
    return ERRORS.get(code)


def explain_text(*texts: str | None) -> SmbError | None:
    return explain(extract_error_code(*texts))
