"""Profielen en instellingen in %APPDATA%\\SMBConnect\\profiles.json.

Wachtwoorden worden hier NOOIT opgeslagen; die gaan naar Windows
Credential Manager.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_VERSION = 1


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "SMBConnect"
    return Path.home() / ".smbconnect"


@dataclass
class ServerProfile:
    name: str = ""                 # weergavenaam, bijv. "NAS woonkamer"
    host: str = ""                 # hostnaam of IP
    ip: str = ""                   # optioneel IP als fallback bij mislukte naamresolutie
    share: str = ""                # sharenaam zonder backslashes
    username: str = ""             # SERVER\gebruiker of MicrosoftAccount\mail
    drive: str = ""                # schijfletter, bijv. "Z:"
    auto_connect: bool = True      # meenemen bij "Alles koppelen" / opstarten
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def unc(self) -> str:
        return f"\\\\{self.host}\\{self.share}" if self.share else f"\\\\{self.host}"

    @classmethod
    def from_dict(cls, data: dict) -> "ServerProfile":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Settings:
    reconnect_at_logon: bool = False
    show_advanced: bool = False


@dataclass
class AppConfig:
    servers: list[ServerProfile] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)

    def find(self, profile_id: str) -> ServerProfile | None:
        return next((s for s in self.servers if s.id == profile_id), None)

    def to_dict(self) -> dict:
        return {
            "version": CONFIG_VERSION,
            "servers": [asdict(s) for s in self.servers],
            "settings": asdict(self.settings),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        servers = [ServerProfile.from_dict(s) for s in data.get("servers", []) if isinstance(s, dict)]
        known = {f.name for f in fields(Settings)}
        settings = Settings(**{k: v for k, v in data.get("settings", {}).items() if k in known})
        return cls(servers=servers, settings=settings)


def config_path() -> Path:
    return config_dir() / "profiles.json"


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            return AppConfig.from_dict(json.load(fh))
    except FileNotFoundError:
        return AppConfig()
    except (OSError, ValueError):
        # Corrupt bestand: bewaar een kopie en begin opnieuw.
        try:
            path.replace(path.with_suffix(".corrupt.json"))
        except OSError:
            pass
        return AppConfig()


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg.to_dict(), fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
