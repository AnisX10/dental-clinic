"""cli init-prod guard helpers: demo detection + production password policy."""
import pytest

from app.cli import _demo_users_present, _prod_password_problem
from app.core.db import get_session_factory
from app.core.services import create_user


def _seed(db, username: str):
    create_user(db, username=username, password="totally-secret-1" + username.replace("-", "x"),
                full_name="Demo", role="dentiste", is_owner=True)


def test_demo_users_detected(client):
    db = get_session_factory()()
    try:
        _seed(db, "drbenali")
        db.commit()
        assert _demo_users_present(db) == ["drbenali"]
    finally:
        db.close()


def test_no_demo_users_in_clean_db(client):
    db = get_session_factory()()
    try:
        assert _demo_users_present(db) == []
    finally:
        db.close()


@pytest.mark.parametrize("password,expected", [
    ("short1!", True),
    ("password123", True),
    ("changeme12345", True),
    ("Dr#Benali-2026", False),
    ("Cl!nic-2026", False),
])
def test_prod_password_policy(password, expected):
    assert (_prod_password_problem(password) is not None) == expected


def test_init_prod_refuses_demo_user(owner_client, users, monkeypatch, capsys):
    """A database with demo accounts is rejected unless --force."""
    import argparse

    from app.cli import _init_prod

    _seed_for_run(owner_client)
    args = argparse.Namespace(
        command="init-prod", username="prodowner", password="Prod#Pass-2026",
        full_name="Prod Owner", force=False,
    )
    assert _init_prod(args) == 1
    assert "DEMO" in capsys.readouterr().err


def _seed_for_run(client):
    from app.core.db import get_session_factory
    from app.core.services import create_user

    db = get_session_factory()()
    try:
        create_user(db, username="drbenali", password="Demo-Pass-2026", full_name="Dr Demo", role="dentiste", is_owner=True)
        db.commit()
    finally:
        db.close()


def test_init_prod_creates_owner_and_audits(client, capsys):
    """Clean database: owner created, catalog seeded, audit printed."""
    import argparse

    from app.cli import _init_prod
    from app.core.db import get_session_factory

    args = argparse.Namespace(
        command="init-prod", username="prodowner", password="Prod#Pass-2026",
        full_name="Prod Owner", force=False,
    )
    assert _init_prod(args) == 0
    out = capsys.readouterr().out
    assert "Owner created: prodowner" in out
    assert "[OK] Frontend build present" in out

    db = get_session_factory()()
    try:
        from sqlalchemy import select

        from app.core.models import User

        row = db.execute(select(User).where(User.username == "prodowner")).scalar_one()
        assert row.is_owner and row.role == "dentiste"
    finally:
        db.close()


def test_init_prod_update_never_adds_second_owner(owner_client, users, capsys):
    """A different username during repair must not silently create another owner."""
    import argparse

    from sqlalchemy import select

    from app.cli import _init_prod
    from app.core.db import get_session_factory
    from app.core.models import User

    args = argparse.Namespace(
        command="init-prod", username="unexpected-owner", password="Prod#Pass-2026",
        full_name="Unexpected Owner", force=False,
    )
    assert _init_prod(args) == 0
    assert "no additional owner" in capsys.readouterr().out.lower()

    db = get_session_factory()()
    try:
        owners = db.execute(select(User).where(User.is_owner.is_(True))).scalars().all()
        assert [owner.username for owner in owners] == ["owner"]
    finally:
        db.close()


def test_launcher_refuses_empty_production_database(client):
    """An interrupted install must not fall back to a shared default password."""
    import pytest

    from sqlalchemy import select

    from app.core.db import get_session_factory
    from app.core.models import User
    from app.launcher import ensure_database_bootstrapped

    with pytest.raises(RuntimeError, match="No clinic owner account exists"):
        ensure_database_bootstrapped()

    db = get_session_factory()()
    try:
        assert db.execute(select(User)).scalars().all() == []
    finally:
        db.close()
