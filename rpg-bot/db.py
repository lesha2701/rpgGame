from typing import Optional

import asyncpg

from config import get_bot_settings

settings = get_bot_settings()

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_user_by_telegram_id(telegram_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)


async def get_user_by_username(username: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM users WHERE username = $1", username)


async def set_ban_status(telegram_id: int, is_banned: bool) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "UPDATE users SET is_banned = $2, updated_at = now() WHERE telegram_id = $1 RETURNING *",
        telegram_id, is_banned,
    )


async def give_coins(telegram_id: int, amount: int, description: str) -> Optional[asyncpg.Record]:
    """Mirrors rpg-backend's wallet_service.credit_coins (lock, mutate,
    ledger row) in raw SQL, same as the football bot's own give_coins —
    the bot talks to Postgres directly (see this project's CLAUDE.md-to-be
    on bot architecture), it does not call back into the backend API."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1 FOR UPDATE", telegram_id)
            if user is None:
                return None
            new_balance = user["balance"] + amount
            await conn.execute(
                "UPDATE users SET balance = $2, updated_at = now() WHERE id = $1", user["id"], new_balance
            )
            await conn.execute(
                """INSERT INTO coin_transactions
                   (user_id, amount, balance_before, balance_after, type, description, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, 'admin_grant', $5, now(), now())""",
                user["id"], amount, user["balance"], new_balance, description,
            )
            return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user["id"])


async def get_hero_summary(user_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        """SELECT uh.level, uh.xp, coalesce(uh.name, ht.name) AS hero_name
           FROM user_heroes uh JOIN hero_templates ht ON ht.id = uh.hero_template_id
           WHERE uh.id = (SELECT active_hero_id FROM users WHERE id = $1)""",
        user_id,
    )


async def get_profile_stats(user_id: int) -> dict:
    pool = await get_pool()
    arena_wins = await pool.fetchval("SELECT count(*) FROM arena_matches WHERE winner_user_id = $1", user_id)
    campaign_nodes_cleared = await pool.fetchval(
        "SELECT count(*) FROM user_campaign_node_clears WHERE user_id = $1", user_id
    )
    return {"arena_wins": arena_wins, "campaign_nodes_cleared": campaign_nodes_cleared}


async def get_stats() -> dict:
    pool = await get_pool()
    total_users = await pool.fetchval("SELECT count(*) FROM users")
    total_heroes = await pool.fetchval("SELECT count(*) FROM user_heroes")
    total_campaign_clears = await pool.fetchval("SELECT coalesce(sum(clear_count), 0) FROM user_campaign_node_clears")
    total_arena_matches = await pool.fetchval("SELECT count(*) FROM arena_matches")
    coins_in_circulation = await pool.fetchval("SELECT coalesce(sum(balance), 0) FROM users")
    return {
        "total_users": total_users,
        "total_heroes": total_heroes,
        "total_campaign_clears": total_campaign_clears,
        "total_arena_matches": total_arena_matches,
        "coins_in_circulation": coins_in_circulation,
    }
