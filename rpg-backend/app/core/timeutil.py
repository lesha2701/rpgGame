from datetime import datetime, timezone


def ensure_aware(dt: datetime) -> datetime:
    """Ported from the football app's app/core/timeutil.py: SQLite (used by
    the test suite) returns naive datetimes even for DateTime(timezone=True)
    columns; Postgres does not. Every naive datetime in this codebase is UTC
    by convention (see models/mixins.py:utcnow), so treating naive as UTC
    here keeps comparisons correct on both backends."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
