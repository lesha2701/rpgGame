def assert_not_football_database(database_url: str) -> None:
    """Redundant, cheap safety net on top of RPG_DATABASE_URL having no
    default (see config.py): even a correctly-set env var that was
    copy-pasted from the football app's .env is caught here before the app
    or Alembic ever opens a connection. Called from both app/main.py and
    alembic/env.py."""
    if "footycards" in database_url:
        raise RuntimeError(
            "Refusing to run: RPG_DATABASE_URL resolves to the football app's "
            "database ('footycards'). This must point at the isolated rpg_game "
            "database instead — check RPG_DATABASE_URL."
        )
