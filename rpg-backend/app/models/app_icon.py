from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class AppIcon(Base, TimestampMixin):
    """One admin-uploadable icon slot for a fixed UI element — the bottom
    nav's 5 tabs, the Battle hub's mode/mini-game rows, and the More
    page's rows. `key` is a stable identifier the frontend already knows
    at build time (e.g. "nav_hero", "minigame_memory") and looks up by;
    `label` is display-only, for the admin list. The set of keys is fixed
    and seeded once (see seed.py's APP_ICONS) — there is no "create a new
    icon slot" flow, since a key with no matching frontend UI element
    would just be dead data. `image_path` is nullable: every slot starts
    unset, and the frontend renders ArtFrame's plain empty-state wash
    (never an emoji or procedural drawing) until an admin uploads one."""

    __tablename__ = "app_icons"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
