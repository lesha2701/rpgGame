"""Renames item_templates from "<Slot> N тира (rarity)" to a flavorful
name that's a pure function of (slot, tier) — rarity/tier no longer belong
in the name at all, since the card already shows both via its own color/
label and "T{n}" badge (see app/seed.py's ITEM_NAMES_RU docstring for the
full reasoning).

Data migration, scoped narrowly like migration 0014's chest renames: only
rows whose CURRENT name still exactly matches what the OLD seed.py
generator would have produced for that row's own (slot, tier, rarity) are
touched — any item an admin renamed by hand is left completely alone.

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SLOT_NAMES_RU = {
    "weapon": "Меч",
    "helmet": "Шлем",
    "armor": "Доспех",
    "boots": "Сапоги",
    "gloves": "Перчатки",
    "ring": "Кольцо",
    "amulet": "Амулет",
}
_OLD_RARITY_NAMES_RU = {
    "common": "обычный",
    "rare": "редкий",
    "epic": "эпический",
    "legendary": "легендарный",
}

_NEW_ITEM_NAMES_RU = {
    "weapon": {
        1: "Деревянный меч", 2: "Кованый меч", 3: "Стальной клинок", 4: "Клинок стража",
        5: "Меч ветерана", 6: "Рыцарский меч", 7: "Меч чемпиона", 8: "Клинок героя",
        9: "Клинок легенды", 10: "Меч владыки",
    },
    "helmet": {
        1: "Кожаный шлем", 2: "Клёпаный шлем", 3: "Стальной шлем", 4: "Шлем стража",
        5: "Шлем ветерана", 6: "Рыцарский шлем", 7: "Шлем чемпиона", 8: "Венец героя",
        9: "Шлем легенды", 10: "Корона владыки",
    },
    "armor": {
        1: "Стёганый доспех", 2: "Кожаный доспех", 3: "Кольчуга", 4: "Доспех стража",
        5: "Доспех ветерана", 6: "Рыцарские латы", 7: "Латы чемпиона", 8: "Доспех героя",
        9: "Доспех легенды", 10: "Латы владыки",
    },
    "boots": {
        1: "Изношенные сапоги", 2: "Дорожные сапоги", 3: "Кожаные сапоги", 4: "Сапоги стража",
        5: "Сапоги ветерана", 6: "Рыцарские сапоги", 7: "Сапоги чемпиона", 8: "Сапоги героя",
        9: "Сапоги легенды", 10: "Сапоги владыки",
    },
    "gloves": {
        1: "Рваные перчатки", 2: "Кожаные перчатки", 3: "Клёпаные перчатки", 4: "Перчатки стража",
        5: "Перчатки ветерана", 6: "Рыцарские перчатки", 7: "Перчатки чемпиона", 8: "Перчатки героя",
        9: "Перчатки легенды", 10: "Перчатки владыки",
    },
    "ring": {
        1: "Медное кольцо", 2: "Бронзовое кольцо", 3: "Серебряное кольцо", 4: "Кольцо стража",
        5: "Кольцо ветерана", 6: "Рыцарское кольцо", 7: "Кольцо чемпиона", 8: "Кольцо героя",
        9: "Кольцо легенды", 10: "Кольцо владыки",
    },
    "amulet": {
        1: "Костяной амулет", 2: "Медный амулет", 3: "Резной амулет", 4: "Амулет стража",
        5: "Амулет ветерана", 6: "Рыцарский амулет", 7: "Амулет чемпиона", 8: "Амулет героя",
        9: "Амулет легенды", 10: "Амулет владыки",
    },
}


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slot, tier, rarity, name FROM item_templates")).fetchall()

    for row in rows:
        if row.slot not in _OLD_SLOT_NAMES_RU or row.rarity not in _OLD_RARITY_NAMES_RU:
            continue
        old_expected = f"{_OLD_SLOT_NAMES_RU[row.slot]} {row.tier} тира ({_OLD_RARITY_NAMES_RU[row.rarity]})"
        if row.name != old_expected:
            continue  # admin-customized name — leave it alone
        new_name = _NEW_ITEM_NAMES_RU.get(row.slot, {}).get(row.tier)
        if new_name is None:
            continue  # tier outside 1..10 (shouldn't happen — CHECK constraint) — nothing to map to
        conn.execute(sa.text("UPDATE item_templates SET name = :name WHERE id = :id"), {"name": new_name, "id": row.id})


def downgrade() -> None:
    # Best-effort only, same documented limitation as 0014's chest
    # rename: the old (slot, tier, rarity)-derived name is regenerable, but
    # there's no way to tell a genuinely admin-renamed row apart from one
    # this migration touched once the forward pass has run, so downgrade
    # does not attempt to reverse it.
    pass
