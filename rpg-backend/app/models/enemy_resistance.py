from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnemyResistance(Base):
    """One per-status_label damage multiplier for an EnemyTemplate — keyed
    by the same status_label strings BattleSkill.status_label/dot skills
    use (e.g. "burn"). `multiplier` >1.0 = vulnerable, <1.0 = resistant,
    read by battle_engine._apply_skill's dot branch via
    CombatantStats.resistances. No row for a given (enemy, status_label)
    pair means the default 1.0 (no effect) — same absent-means-neutral
    convention as ItemAffix having no row for a stat_type an item doesn't
    grant."""

    __tablename__ = "enemy_resistances"
    __table_args__ = (
        UniqueConstraint("enemy_template_id", "status_label", name="uq_enemy_resistances_template_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enemy_template_id: Mapped[int] = mapped_column(ForeignKey("enemy_templates.id"), nullable=False, index=True)
    status_label: Mapped[str] = mapped_column(String(32), nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)
