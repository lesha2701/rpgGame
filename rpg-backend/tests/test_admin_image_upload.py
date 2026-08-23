from tests.utils import telegram_headers

ADMIN_TELEGRAM_ID = 999000099

# A syntactically-valid, minimal 1x1 PNG — small enough to keep the test
# file readable inline, real enough that content-sniffing wouldn't reject it
# (this backend only checks extension/content-type/size, not pixel data).
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "0000004945"
)


async def _admin_headers(client, bot_token) -> dict:
    headers = telegram_headers(ADMIN_TELEGRAM_ID, bot_token)
    resp = await client.post("/api/v1/auth/session", headers=headers)
    return {"Authorization": f"Bearer {resp.json()['admin_token']}"}


async def test_upload_enemy_image_sets_image_path(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/enemies",
        headers=admin,
        json={"name": "ImgTestEnemy", "level": 1, "hp": 10, "attack": 1, "defense": 1, "speed": 1, "reward_xp": 1, "reward_coins": 1},
    )
    enemy_id = created.json()["id"]
    assert created.json()["image_path"] is None

    uploaded = await client.post(
        f"/api/v1/admin/enemies/{enemy_id}/image",
        headers=admin,
        files={"file": ("goblin.png", TINY_PNG, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    path = uploaded.json()["image_path"]
    assert path is not None
    assert path.startswith("enemies/")
    assert path.endswith(".png")


async def test_upload_rejects_disallowed_extension(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/enemies",
        headers=admin,
        json={"name": "ImgTestEnemy2", "level": 1, "hp": 10, "attack": 1, "defense": 1, "speed": 1, "reward_xp": 1, "reward_coins": 1},
    )
    enemy_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/admin/enemies/{enemy_id}/image",
        headers=admin,
        files={"file": ("goblin.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert resp.status_code == 400


async def test_upload_replaces_previous_image(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/items",
        headers=admin,
        json={"slot": "ring", "tier": 1, "rarity": "common", "name": "ImgTestItem"},
    )
    item_id = created.json()["id"]

    first = await client.post(
        f"/api/v1/admin/items/{item_id}/image",
        headers=admin,
        files={"file": ("a.png", TINY_PNG, "image/png")},
    )
    first_path = first.json()["image_path"]

    second = await client.post(
        f"/api/v1/admin/items/{item_id}/image",
        headers=admin,
        files={"file": ("b.png", TINY_PNG, "image/png")},
    )
    second_path = second.json()["image_path"]

    assert first_path != second_path


async def test_upload_expedition_image(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/expeditions",
        headers=admin,
        json={"name": "ImgTestExpedition", "duration_seconds": 60, "required_hero_level": 1, "reward_xp": 1, "reward_coins": 1},
    )
    expedition_id = created.json()["id"]

    uploaded = await client.post(
        f"/api/v1/admin/expeditions/{expedition_id}/image",
        headers=admin,
        files={"file": ("ruins.png", TINY_PNG, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["image_path"].startswith("expeditions/")


async def test_upload_chest_image(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/chests",
        headers=admin,
        json={
            "slug": "img-test-chest",
            "name": "ImgTestChest",
            "description": "",
            "price": 100,
            "rarity_probabilities": [
                {"rarity": "common", "probability": 0.7},
                {"rarity": "rare", "probability": 0.2},
                {"rarity": "epic", "probability": 0.08},
                {"rarity": "legendary", "probability": 0.02},
            ],
        },
    )
    assert created.status_code == 200, created.text
    chest_id = created.json()["id"]
    assert created.json()["image_path"] is None

    uploaded = await client.post(
        f"/api/v1/admin/chests/{chest_id}/image",
        headers=admin,
        files={"file": ("chest.png", TINY_PNG, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    path = uploaded.json()["image_path"]
    assert path is not None
    assert path.startswith("chests/")
    assert path.endswith(".png")


async def test_static_files_are_served(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/enemies",
        headers=admin,
        json={"name": "ImgTestEnemyServe", "level": 1, "hp": 10, "attack": 1, "defense": 1, "speed": 1, "reward_xp": 1, "reward_coins": 1},
    )
    enemy_id = created.json()["id"]
    uploaded = await client.post(
        f"/api/v1/admin/enemies/{enemy_id}/image",
        headers=admin,
        files={"file": ("goblin.png", TINY_PNG, "image/png")},
    )
    path = uploaded.json()["image_path"]

    served = await client.get(f"/static/{path}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
