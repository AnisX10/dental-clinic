"""Install-time configuration: data/config.json, version source, password check, path guard."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.runtime_config import RuntimeConfig, load_runtime_config, save_runtime_config

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    monkeypatch.delenv("CLINIC_PORT", raising=False)
    monkeypatch.delenv("CLINIC_LAN", raising=False)


def test_defaults_when_missing(tmp_path):
    cfg = load_runtime_config(tmp_path / "config.json")
    assert cfg == RuntimeConfig(port=8000, lan=False)
    assert cfg.bind_host == "127.0.0.1"  # this PC only unless LAN was chosen


def test_lan_binds_all_interfaces(tmp_path):
    path = tmp_path / "config.json"
    save_runtime_config(RuntimeConfig(port=8123, lan=True), path)
    cfg = load_runtime_config(path)
    assert (cfg.port, cfg.lan, cfg.bind_host) == (8123, True, "0.0.0.0")


def test_bom_and_garbage_tolerated(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'\xef\xbb\xbf{"port": 9001, "lan": "true"}')  # BOM from PowerShell/.NET
    assert load_runtime_config(path) == RuntimeConfig(port=9001, lan=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_runtime_config(path) == RuntimeConfig()
    path.write_text('{"port": 80}', encoding="utf-8")  # privileged port -> default
    assert load_runtime_config(path).port == 8000


def test_env_overrides_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    save_runtime_config(RuntimeConfig(port=8123, lan=True), path)
    monkeypatch.setenv("CLINIC_PORT", "8200")
    monkeypatch.setenv("CLINIC_LAN", "0")
    assert load_runtime_config(path) == RuntimeConfig(port=8200, lan=False)


def test_version_comes_from_version_file():
    from app.core.config import APP_VERSION

    expected = (BACKEND.parent / "VERSION").read_text(encoding="utf-8").strip()
    assert APP_VERSION == expected


@pytest.mark.parametrize(
    "password, ok",
    [("short", False), ("password-123", False), ("abcdefghijk1", False), ("Dr#Benali-2026", True)],
)
def test_check_password_command(password, ok):
    env = {**os.environ, "CLINIC_INIT_PASSWORD": password}
    proc = subprocess.run(
        [sys.executable, str(BACKEND / "app" / "cli.py"), "check-password"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert (proc.returncode == 0) is ok, proc.stdout + proc.stderr
    if not ok:
        assert proc.returncode == 2 and proc.stdout.strip()  # French reason shown


@pytest.mark.skipif(os.name != "nt", reason="Windows-only PostgreSQL path limitation")
def test_non_ascii_install_path_is_flagged():
    from app.core.db import unsupported_path_chars

    assert unsupported_path_chars(Path("C:/HKN Dentaire/data")) == ""
    assert unsupported_path_chars(Path("C:/Users/d'Amico (2)/x")) == ""
    assert unsupported_path_chars(Path("C:/Users/Am\u00e9lie/x")) == "\u00e9"
    assert unsupported_path_chars(Path("C:/Users/\u0645\u062d\u0645\u062f/x")) == "\u0645\u062d\u062f"
