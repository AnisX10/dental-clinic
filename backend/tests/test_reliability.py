"""Reliability guards: commit-before-response and stale postmaster.pid recovery."""

import os

from sqlalchemy.orm import Session

from app.core.db import remove_stale_postmaster_pid


def _patient_payload(**overrides):
    data = {"nom": "Commit", "prenom": "Echec", "telephone": "0550 11 22 33"}
    data.update(overrides)
    return data


def test_failed_commit_is_reported_as_error(owner_client, monkeypatch):
    """If the final commit fails, the client must NOT receive a success.

    Regression: with a request-scoped yield dependency FastAPI committed after
    the response was sent, so a failed commit was silently reported as 201.
    """
    from fastapi.testclient import TestClient

    calls = {"n": 0}

    def failing_commit(self):
        calls["n"] += 1
        raise RuntimeError("simulated commit failure (disk full)")

    with TestClient(owner_client.app, raise_server_exceptions=False) as c:
        c.cookies.update(owner_client.cookies)
        monkeypatch.setattr(Session, "commit", failing_commit)
        resp = c.post("/api/patients", json=_patient_payload())
        monkeypatch.undo()

    assert calls["n"] >= 1
    assert resp.status_code >= 500, resp.text

    # Nothing was persisted.
    listing = owner_client.get("/api/patients", params={"q": "Commit"})
    assert listing.status_code == 200
    assert not any(p["nom"] == "Commit" for p in listing.json()["patients"])


def test_stale_pid_dead_process_removed(tmp_path):
    pid_file = tmp_path / "postmaster.pid"
    pid_file.write_text("4194300\n/data\n", encoding="utf-8")  # no such PID
    assert remove_stale_postmaster_pid(tmp_path) is True
    assert not pid_file.exists()


def test_stale_pid_reused_by_other_program_removed(tmp_path):
    """Power-cut case: the PID is alive but is not postgres (here: pytest)."""
    pid_file = tmp_path / "postmaster.pid"
    pid_file.write_text(f"{os.getpid()}\n/data\n", encoding="utf-8")
    assert remove_stale_postmaster_pid(tmp_path) is True
    assert not pid_file.exists()


def test_stale_pid_garbage_removed(tmp_path):
    pid_file = tmp_path / "postmaster.pid"
    pid_file.write_text("not-a-pid\n", encoding="utf-8")
    assert remove_stale_postmaster_pid(tmp_path) is True
    assert not pid_file.exists()


def test_live_postgres_pid_is_kept(client, tmp_path):
    """The pid file of a RUNNING postgres must never be removed.

    Regression: an early version deleted it unconditionally, which made the
    running server shut itself down ("data directory lock file is invalid").
    Uses the real pid file of the test cluster the `client` fixture runs.
    """
    import shutil

    from tests.conftest import BACKEND_DIR

    live = BACKEND_DIR.parent / "data" / "pgdata-test" / "postmaster.pid"
    if not live.is_file():
        import pytest

        pytest.skip("test cluster is not the bundled pgserver")
    copy = tmp_path / "postmaster.pid"
    shutil.copy2(live, copy)  # keeps mtime
    assert remove_stale_postmaster_pid(tmp_path) is False
    assert copy.is_file()


def test_no_pid_file_is_noop(tmp_path):
    assert remove_stale_postmaster_pid(tmp_path) is False
