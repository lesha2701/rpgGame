"""Regression coverage for app/seed.py's idempotent get-or-create helpers —
not full end-to-end seed() runs (that uses its own AsyncSessionLocal bound
to the real configured engine, not the test session), just the query
functions directly, since this is the third time a query touching a
lazy="joined" *collection* relationship (ItemTemplate.affixes here) forgot
.unique() and only surfaced when actually run against Postgres."""

from app.models.enums import EquipmentSlot, Rarity
from app.seed import _get_or_create_chest, _get_or_create_free_chest, _get_or_create_item_template


async def test_get_or_create_item_template_is_idempotent(db_session):
    first = await _get_or_create_item_template(db_session, EquipmentSlot.weapon, 1, Rarity.common, 1)
    await db_session.commit()
    second = await _get_or_create_item_template(db_session, EquipmentSlot.weapon, 1, Rarity.common, 1)
    await db_session.commit()
    assert first.id == second.id


async def test_get_or_create_chest_is_idempotent(db_session):
    first = await _get_or_create_chest(db_session, quality=1)
    await db_session.commit()
    second = await _get_or_create_chest(db_session, quality=1)
    await db_session.commit()
    assert first.id == second.id
    assert len(second.rarity_probabilities) == 4


async def test_get_or_create_free_chest_is_idempotent(db_session):
    first = await _get_or_create_free_chest(db_session)
    await db_session.commit()
    second = await _get_or_create_free_chest(db_session)
    await db_session.commit()
    assert first.id == second.id
    assert first.slug == "free-chest"
    assert first.price == 0
    assert len(second.rarity_probabilities) == 4
