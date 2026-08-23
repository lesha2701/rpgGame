from pydantic import BaseModel


class HeroProgressOut(BaseModel):
    """A hero+wallet snapshot, always read live (never a stored/cached
    value) — the same handful of fields Battle/Expedition/Quest claim
    responses all needed independently. Existing endpoints (BattleOut,
    UserExpeditionOut) keep their own already-shipped flat field names
    (hero_level/hero_xp/balance) rather than switching to this nested shape
    — that would be a breaking response-shape change for no functional
    gain. New endpoints (Quest) use this directly. See
    hero_service.hero_progress_out(), the one function that builds it."""

    level: int
    xp: int
    xp_to_next_level: int | None
    balance: int
