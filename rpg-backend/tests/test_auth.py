from tests.utils import make_init_data, telegram_headers

from app.core.security import TelegramAuthError, validate_init_data


def test_valid_init_data_parses_user(bot_token):
    init_data = make_init_data({"id": 12345, "username": "alice"}, bot_token)
    user = validate_init_data(init_data, bot_token)
    assert user.id == 12345
    assert user.username == "alice"


def test_tampered_init_data_is_rejected(bot_token):
    init_data = make_init_data({"id": 12345, "username": "alice"}, bot_token)
    tampered = init_data.replace("alice", "mallory")
    try:
        validate_init_data(tampered, bot_token)
        assert False, "expected TelegramAuthError"
    except TelegramAuthError:
        pass


async def test_registration_creates_user(client, bot_token):
    headers = telegram_headers(555001, bot_token, username="newplayer")
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    body = resp.json()["user"]
    assert body["telegram_id"] == 555001
    assert body["active_hero"] is None


async def test_repeat_login_reuses_same_user(client, bot_token):
    headers = telegram_headers(555002, bot_token, username="returning")
    first = await client.post("/api/v1/auth/session", headers=headers)
    second = await client.post("/api/v1/auth/session", headers=headers)
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


async def test_dev_mode_login_without_telegram(client):
    resp = await client.get("/api/v1/auth/me", headers={"X-Dev-Mode": "true"})
    assert resp.status_code == 200
    assert resp.json()["telegram_id"] == 999000001


async def test_missing_auth_is_rejected(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
