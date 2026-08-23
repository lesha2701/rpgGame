"""Leaderboards: read-only, derived entirely from existing tables — no
`leaderboards`/`leaderboard_entries`/`user_statistics` table, no stored
rank, no rating/MMR. Each type builds a small ranked subquery (Postgres's
`RANK() OVER (ORDER BY ...)` window function, computed once, reused for
both the paginated entry list and the "my rank" lookup) rather than
replicating the tie-break comparison in Python or issuing a second query
shaped differently for "my rank" than for the list. See ARCHITECTURE.md's
Stage 11 section for why RANK() over a fully deterministic 3-key order
(the same tie-break requirement every ranked list in this codebase already
follows) makes ROW_NUMBER()-style duplicate ranks structurally impossible
here — every row's sort key is already unique because the final tie-break
is always User.id.

Aggregation happens strictly *before* any join to display-only tables
(User/UserHero/HeroTemplate) — each win-counting subquery groups its own
table in isolation first, so joining it to one-to-one display data
afterward can never multiply rows. Never one giant multi-table JOIN that
aggregates across a fan-out."""

from typing import Callable, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena_match import ArenaMatch
from app.models.battle import Battle
from app.models.enums import ArenaMatchStatus, BattleResult
from app.models.hero_template import HeroTemplate
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.leaderboard import LeaderboardEntryOut, LeaderboardHeroOut, LeaderboardOut

LEADERBOARD_TYPES = ("level", "pve_wins", "arena_wins", "coins")


def _display_columns():
    return (
        User.id.label("user_id"),
        User.username.label("username"),
        HeroTemplate.name.label("hero_name"),
        UserHero.level.label("hero_level"),
    )


def _level_query() -> Select:
    order = (UserHero.level.desc(), UserHero.xp.desc(), User.id.asc())
    return (
        select(
            *_display_columns(),
            UserHero.level.label("value"),
            func.rank().over(order_by=order).label("rank"),
        )
        .select_from(UserHero)
        .join(User, User.id == UserHero.user_id)
        .join(HeroTemplate, HeroTemplate.id == UserHero.hero_template_id)
    )


def _pve_wins_query() -> Select:
    wins = (
        select(Battle.user_id.label("user_id"), func.count(Battle.id).label("wins"))
        .where(Battle.result == BattleResult.won)
        .group_by(Battle.user_id)
        .subquery()
    )
    order = (wins.c.wins.desc(), UserHero.level.desc().nullslast(), User.id.asc())
    return (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            HeroTemplate.name.label("hero_name"),
            UserHero.level.label("hero_level"),
            wins.c.wins.label("value"),
            func.rank().over(order_by=order).label("rank"),
        )
        .select_from(wins)
        .join(User, User.id == wins.c.user_id)
        .outerjoin(UserHero, UserHero.user_id == User.id)
        .outerjoin(HeroTemplate, HeroTemplate.id == UserHero.hero_template_id)
    )


def _arena_wins_query() -> Select:
    wins = (
        select(ArenaMatch.winner_user_id.label("user_id"), func.count(ArenaMatch.id).label("wins"))
        .where(ArenaMatch.status == ArenaMatchStatus.finished, ArenaMatch.winner_user_id.is_not(None))
        .group_by(ArenaMatch.winner_user_id)
        .subquery()
    )
    order = (wins.c.wins.desc(), UserHero.level.desc().nullslast(), User.id.asc())
    return (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            HeroTemplate.name.label("hero_name"),
            UserHero.level.label("hero_level"),
            wins.c.wins.label("value"),
            func.rank().over(order_by=order).label("rank"),
        )
        .select_from(wins)
        .join(User, User.id == wins.c.user_id)
        .outerjoin(UserHero, UserHero.user_id == User.id)
        .outerjoin(HeroTemplate, HeroTemplate.id == UserHero.hero_template_id)
    )


def _coins_query() -> Select:
    order = (User.balance.desc(), User.id.asc())
    return (
        select(
            *_display_columns(),
            User.balance.label("value"),
            func.rank().over(order_by=order).label("rank"),
        )
        .select_from(User)
        .outerjoin(UserHero, UserHero.user_id == User.id)
        .outerjoin(HeroTemplate, HeroTemplate.id == UserHero.hero_template_id)
    )


_QUERY_BUILDERS: dict[str, Callable[[], Select]] = {
    "level": _level_query,
    "pve_wins": _pve_wins_query,
    "arena_wins": _arena_wins_query,
    "coins": _coins_query,
}


async def get_leaderboard(
    db: AsyncSession, leaderboard_type: str, limit: int, offset: int, viewer_user_id: Optional[int]
) -> LeaderboardOut:
    builder = _QUERY_BUILDERS.get(leaderboard_type)
    if builder is None:
        raise ValueError(f"Unknown leaderboard type: {leaderboard_type}")

    ranked = builder().subquery()

    total = (await db.execute(select(func.count()).select_from(ranked))).scalar_one()

    rows = (
        await db.execute(select(ranked).order_by(ranked.c.rank.asc()).limit(limit).offset(offset))
    ).all()
    entries = [
        LeaderboardEntryOut(
            rank=row.rank,
            user_id=row.user_id,
            username=row.username,
            hero=LeaderboardHeroOut(name=row.hero_name, level=row.hero_level) if row.hero_name is not None else None,
            value=row.value,
        )
        for row in rows
    ]

    my_rank: Optional[int] = None
    my_value = 0
    if viewer_user_id is not None:
        my_row = (await db.execute(select(ranked).where(ranked.c.user_id == viewer_user_id))).first()
        if my_row is not None:
            my_rank = my_row.rank
            my_value = my_row.value

    return LeaderboardOut(
        type=leaderboard_type,
        entries=entries,
        total=total,
        limit=limit,
        offset=offset,
        my_rank=my_rank,
        my_value=my_value,
    )
