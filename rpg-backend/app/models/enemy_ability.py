from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import SkillType
from app.models.mixins import TimestampMixin


class EnemyAbility(Base, TimestampMixin):
    """One move in an enemy's catalog — structurally mirrors
    SkillDefinition (same skill_type/power/cooldown_turns/buff_stat/
    status_label shape, resolved by the exact same battle_engine._apply_skill
    branches via campaign_battle_service's BattleSkill conversion), but
    belongs to an EnemyTemplate instead of a CharacterClass and has no
    per-level power growth — an enemy's numbers are authored directly for
    its one fixed level, same as EnemyTemplate's own stat columns (see
    that model's docstring).

    `code` is what EnemyTemplate.behavior_pattern's ordered list
    references (e.g. ["basic_attack", "heavy_strike", "recover"]) — the
    pattern cycles through these codes each round, falling back to Basic
    Attack if the next one is on cooldown, same tolerance
    _pick_ready_skill/arena_service already apply to the hero side."""

    __tablename__ = "enemy_abilities"
    __table_args__ = (UniqueConstraint("enemy_template_id", "code", name="uq_enemy_abilities_template_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enemy_template_id: Mapped[int] = mapped_column(ForeignKey("enemy_templates.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(SAEnum(SkillType, name="skill_type"), nullable=False)

    power: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    cooldown_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buff_stat: Mapped[str] = mapped_column(String(16), nullable=False, default="attack", server_default="attack")
    status_label: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
