from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ItemEffectTrigger, ItemEffectType
from app.models.mixins import TimestampMixin


class ItemEffect(Base, TimestampMixin):
    """One build-enabling behavior an ItemTemplate grants in campaign
    combat — resolved by a small explicit trigger->handler dict in
    campaign_battle_service.py, deliberately not a scripting engine
    (Stage 13 spec §10). An item can carry several rows (e.g. one
    on_crit apply_status + one damage_bonus_vs_status, letting an
    Ember Ring both apply Burn on crit and hit harder against
    already-burning enemies — the synergy example from the spec).

    Unlike ItemAffix (a flat stat pointer, unchanged by Stage 13),
    ItemEffect is entirely additive/opt-in: an ItemTemplate with zero
    ItemEffect rows behaves exactly as it did before this table existed.

    What `magnitude`/`status_label`/`duration_turns` mean depends on
    effect_type:
      - apply_status: status_label + magnitude (per-tick power) +
        duration_turns describe the status applied.
      - damage_bonus_vs_status: magnitude is a damage multiplier applied
        when the target already carries status_label.
      - shield_bonus_pct / lifesteal_pct: magnitude is a percentage
        (0-100); status_label/duration_turns are unused (nullable)."""

    __tablename__ = "item_effects"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    trigger: Mapped[ItemEffectTrigger] = mapped_column(
        SAEnum(ItemEffectTrigger, name="item_effect_trigger"), nullable=False
    )
    effect_type: Mapped[ItemEffectType] = mapped_column(
        SAEnum(ItemEffectType, name="item_effect_type"), nullable=False
    )

    status_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    magnitude: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    duration_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
