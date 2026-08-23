from tests.factories import get_user_by_telegram_id
from tests.utils import telegram_headers

ADMIN_TELEGRAM_ID = 999000099


async def _admin_headers(client, bot_token) -> dict:
    headers = telegram_headers(ADMIN_TELEGRAM_ID, bot_token)
    resp = await client.post("/api/v1/auth/session", headers=headers)
    return {"Authorization": f"Bearer {resp.json()['admin_token']}"}


async def _make_user(client, bot_token, telegram_id: int, username: str | None = None):
    headers = telegram_headers(telegram_id, bot_token, username=username)
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    return resp.json()["user"]["id"]


async def test_list_users_and_search_by_username(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    await _make_user(client, bot_token, 50900, username="grognak_the_barbarian")

    listed = await client.get("/api/v1/admin/users", headers=admin)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert any(u["username"] == "grognak_the_barbarian" for u in body["users"])

    searched = await client.get("/api/v1/admin/users?search=grognak", headers=admin)
    assert searched.status_code == 200
    assert [u["username"] for u in searched.json()["users"]] == ["grognak_the_barbarian"]


async def test_search_by_telegram_id(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    await _make_user(client, bot_token, 50901)

    searched = await client.get("/api/v1/admin/users?search=50901", headers=admin)
    assert [u["telegram_id"] for u in searched.json()["users"]] == [50901]


async def test_user_detail_includes_statistics(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50902)

    detail = await client.get(f"/api/v1/admin/users/{user_id}", headers=admin)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == user_id
    assert body["statistics"]["battles"] == {"played": 0, "wins": 0, "losses": 0}


async def test_user_detail_404_for_unknown_id(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    resp = await client.get("/api/v1/admin/users/999999", headers=admin)
    assert resp.status_code == 404


async def test_grant_coins_credits_balance(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50903)

    resp = await client.post(f"/api/v1/admin/users/{user_id}/grant-coins", headers=admin, json={"amount": 250})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 250

    again = await client.post(f"/api/v1/admin/users/{user_id}/grant-coins", headers=admin, json={"amount": 50})
    assert again.json()["balance"] == 300


async def test_grant_coins_rejects_non_positive_amount(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50904)

    resp = await client.post(f"/api/v1/admin/users/{user_id}/grant-coins", headers=admin, json={"amount": 0})
    assert resp.status_code == 422


async def test_deduct_coins_debits_balance(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50907)

    await client.post(f"/api/v1/admin/users/{user_id}/grant-coins", headers=admin, json={"amount": 300})

    resp = await client.post(f"/api/v1/admin/users/{user_id}/deduct-coins", headers=admin, json={"amount": 120})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 180


async def test_deduct_coins_rejects_insufficient_balance(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50908)

    resp = await client.post(f"/api/v1/admin/users/{user_id}/deduct-coins", headers=admin, json={"amount": 50})
    assert resp.status_code == 400


async def test_deduct_coins_rejects_non_positive_amount(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50909)

    resp = await client.post(f"/api/v1/admin/users/{user_id}/deduct-coins", headers=admin, json={"amount": 0})
    assert resp.status_code == 422


async def test_toggle_ban_blocks_login(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    user_id = await _make_user(client, bot_token, 50905)

    toggled = await client.post(f"/api/v1/admin/users/{user_id}/toggle-ban", headers=admin)
    assert toggled.status_code == 200
    assert toggled.json()["is_banned"] is True

    blocked = await client.post("/api/v1/auth/session", headers=telegram_headers(50905, bot_token))
    assert blocked.status_code == 403

    untoggled = await client.post(f"/api/v1/admin/users/{user_id}/toggle-ban", headers=admin)
    assert untoggled.json()["is_banned"] is False

    restored = await client.post("/api/v1/auth/session", headers=telegram_headers(50905, bot_token))
    assert restored.status_code == 200


async def test_cannot_ban_an_admin(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    admin_user = await get_user_by_telegram_id(db_session, ADMIN_TELEGRAM_ID)

    resp = await client.post(f"/api/v1/admin/users/{admin_user.id}/toggle-ban", headers=admin)
    assert resp.status_code == 409


async def test_user_stats_aggregate(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)
    await _make_user(client, bot_token, 50906)

    resp = await client.get("/api/v1/admin/users/stats", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] >= 2  # admin + the user just created
    assert body["admin_users"] >= 1
