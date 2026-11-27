"""Per-install runtime settings written by Setup: ``data/config.json``.

    {"port": 8000, "lan": false}

- ``port``: the single HTTP port for API + UI.
- ``lan``:  False = only this PC can open the app (bind 127.0.0.1);
            True  = other PCs on the clinic network can connect (bind 0.0.0.0).

Read by the launcher here, and by ``Common.cs`` / ``stop.bat`` /
``start_silent.vbs`` with the same defaults. ``CLINIC_PORT`` / ``CLINIC_LAN``
environment variables override the file (support / dev use).
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("clinic")

DEFAULT_PORT = 8000
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "data" / "config.json"


@dataclass(frozen=True)
class RuntimeConfig:
    port: int = DEFAULT_PORT
    lan: bool = False

    @property
    def bind_host(self) -> str:
        return "0.0.0.0" if self.lan else "127.0.0.1"


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _valid_port(value) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1024 <= port <= 65535 else None


def load_runtime_config(path: Path | None = None) -> RuntimeConfig:
    path = path or CONFIG_PATH
    port, lan = DEFAULT_PORT, False
    if path.is_file():
        try:
            # utf-8-sig: tolerate a BOM written by PowerShell / .NET.
            data = json.loads(path.read_text(encoding="utf-8-sig") or "{}")
            if isinstance(data, dict):
                port = _valid_port(data.get("port")) or DEFAULT_PORT
                lan = _as_bool(data.get("lan", False))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable %s (%s); using defaults", path, exc)
    env_port = _valid_port(os.environ.get("CLINIC_PORT"))
    if env_port:
        port = env_port
    if os.environ.get("CLINIC_LAN"):
        lan = _as_bool(os.environ["CLINIC_LAN"])
    return RuntimeConfig(port=port, lan=lan)


def save_runtime_config(cfg: RuntimeConfig, path: Path | None = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"port": cfg.port, "lan": cfg.lan}, indent=2), encoding="utf-8")
    os.replace(tmp, path)
