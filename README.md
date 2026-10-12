# SMB Connect

Windows 11-app om gedeelde mappen (SMB) tussen Windows-pc's in je lokale netwerk
met één klik te koppelen, te diagnosticeren en te repareren. Sinds Windows 11 gaat dit
via Verkenner vaak mis door strengere standaardinstellingen (SMB-signing verplicht,
gasttoegang geblokkeerd, Microsoft-accounts met alleen PIN). SMB Connect laat zien wát er
misgaat en hoe je het oplost.

> **Status:** Tab 2 (Diagnose) is klaar. Tab 1 (Koppelen) en Tab 3 (Deze machine als
> server) volgen.

## Functies

### Tab 2 – Diagnose (per server)
Controleert stap voor stap en toont per stap groen / oranje / rood met uitleg en een
voorgestelde oplossing:

| Stap | Hoe |
|---|---|
| Naamresolutie | `[System.Net.Dns]::GetHostAddresses()`; valt terug op het opgegeven IP als de naam niet gevonden wordt |
| Ping / bereikbaarheid | `Test-NetConnection` (ping geblokkeerd maar SMB open = oranje, geen probleem) |
| Poort 445 | `Test-NetConnection -Port 445` |
| Authenticatie | Tijdelijke verbinding met `New-SmbMapping` (zonder schijfletter), daarna weer verbroken. Foutcodes 1326, 1272, 53, 67, 1219, 5 en meer worden vertaald naar begrijpelijke uitleg |
| SMB-dialect | `Get-SmbConnection` (3.x groen, 2.x oranje, 1.x rood) |
| Accounttype | Waarschuwing bij Microsoft-accounts: SMB vereist het echte wachtwoord, geen PIN |
| Lokale client-instellingen | `Get-SmbClientConfiguration`: `RequireSecuritySignature`, `EnableInsecureGuestLogons` en het beleid `AllowInsecureGuestAuth` |

Met **Rapport kopiëren** zet je de uitkomst als tekst op het klembord.

### Log-venster
Onderin staan alle uitgevoerde commando's en hun uitvoer, handig bij het oplossen van
problemen. Wachtwoorden worden nooit gelogd. Met **Opslaan…** bewaar je het log als
tekstbestand.

## Gebruik

1. Start `SMBConnect.exe` (of `python run.py`, zie hieronder).
2. Ga naar **Diagnose**, vul de server (naam of IP), de share en eventueel een
   gebruikersnaam in.
   * Gebruikersnaam: `SERVER\gebruiker` voor een lokaal account op de server, of
     `MicrosoftAccount\naam@outlook.com` voor een Microsoft-account.
   * Wachtwoord is optioneel en wordt alleen voor deze test gebruikt (niet opgeslagen).
     Laat je het leeg, dan gebruikt Windows de opgeslagen inloggegevens of je eigen
     aanmelding.
3. Klik op **Diagnose starten**.

## Uitvoeren vanuit de broncode

Vereist: Windows 10/11 en Python 3.10 of nieuwer (python.org, met tkinter, dat standaard
meegeleverd wordt).

```powershell
python run.py
```

## Bouwen tot één .exe

Dubbelklik op `build.bat`, of in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Het script maakt een virtuele omgeving (`.venv`), installeert PyInstaller en pytest, draait
de tests en bouwt `dist\SMBConnect.exe` (één bestand, zonder consolevenster).

## Tests

```powershell
python -m pip install pytest
python -m pytest
```

De tests draaien ook op Linux/macOS: de PowerShell-aanroepen worden daarin vervangen door
nep-antwoorden.

## Ontwerpkeuzes

* **Geen admin voor de hele app.** Alleen acties die het systeem wijzigen vragen via UAC
  om adminrechten (`smbconnect/elevate.py`), en die worden eerst bevestigd.
* **Geen wachtwoorden in bestanden.** Profielen staan in
  `%APPDATA%\SMBConnect\profiles.json`; wachtwoorden gaan naar Windows Credential Manager.
* **Wachtwoorden niet op de commandoregel.** Voor tests gaat het wachtwoord via een
  omgevingsvariabele naar het PowerShell-proces, zodat het niet zichtbaar is in
  procesoverzichten of in het log.

## Projectstructuur

```
run.py                    startpunt (ook voor PyInstaller)
build.ps1 / build.bat     build-script voor SMBConnect.exe
smbconnect/
  runner.py               uitvoeren van PowerShell / net / cmdkey + logging
  elevate.py              UAC-elevatie voor admin-acties
  config.py               profielen in %APPDATA%\SMBConnect
  errors.py               foutcodes → begrijpelijke uitleg
  diagnose.py             diagnose-stappen (los van de UI, testbaar)
  ui/
    app.py                hoofdvenster, tabs, log, achtergrondtaken
    theme.py              donker thema
    widgets.py            log-paneel, scrollframe, statusbolletje
    diagnose_tab.py       Tab 2
tests/                    pytest-tests met nep-runner
```
