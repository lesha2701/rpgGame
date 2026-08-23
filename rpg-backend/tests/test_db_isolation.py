"""No real database is involved here — these exercise the config/guard
layer directly to prove the RPG backend cannot end up pointed at the
football app's database, whether an env var is wrong, missing, or leaked
from the wrong process."""

import os

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.db_guard import assert_not_football_database


def test_football_database_url_env_var_is_ignored():
    """Even if the football app's DATABASE_URL leaked into this process's
    environment (e.g. a copy-pasted env_file line), RPG Settings must not
    pick it up — it only ever reads RPG_DATABASE_URL, never DATABASE_URL."""
    assert "DATABASE_URL" not in os.environ, "conftest.py must not set DATABASE_URL"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:1234@postgres:5432/footycards"
    try:
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url == "sqlite+aiosqlite://"  # from RPG_DATABASE_URL, set by conftest
    finally:
        del os.environ["DATABASE_URL"]


def test_missing_rpg_database_url_refuses_to_start():
    """It must be impossible to boot this backend against the football DB
    merely by forgetting to set an env var — a missing RPG_DATABASE_URL
    must fail loudly at Settings construction, not fall back to a default."""
    original = os.environ.pop("RPG_DATABASE_URL")
    try:
        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # type: ignore[call-arg]
    finally:
        os.environ["RPG_DATABASE_URL"] = original


def test_guard_rejects_a_url_naming_the_football_database():
    with pytest.raises(RuntimeError, match="footycards"):
        assert_not_football_database("postgresql+asyncpg://rpg_admin:x@postgres:5432/footycards")


def test_guard_allows_the_rpg_database():
    assert_not_football_database("postgresql+asyncpg://rpg_admin:x@postgres:5432/rpg_game")  # must not raise


def test_guard_is_wired_into_app_startup_and_alembic_env():
    """Static check that both entry points actually call the guard, so this
    protection can't silently be dropped by a future edit to either file.
    Reads alembic/env.py as plain text rather than importing it — it's a
    standalone script for the alembic CLI, not a package module, and the
    directory name "alembic" would otherwise collide with the installed
    alembic package on sys.path."""
    import inspect
    from pathlib import Path

    import app.main as main_module

    assert "assert_not_football_database" in inspect.getsource(main_module)

    env_py = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    assert "assert_not_football_database" in env_py.read_text()
