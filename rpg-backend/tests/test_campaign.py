from tests.factories import (
    create_boss_phase,
    create_campaign_node,
    create_campaign_node_edge,
    create_campaign_region,
    create_class,
    create_enemy_ability,
    create_enemy_template,
    create_hero_template,
    create_item_effect,
    create_item_template,
    create_skill_definition,
    get_user_by_telegram_id,
    grant_item_to_user,
    set_hero_level,
)
from tests.utils import telegram_headers

from app.models.enums import CampaignNodeType, ItemEffectTrigger, ItemEffectType, SkillType
from app.services.inventory_service import equip_item


async def _make_hero(client, db_session, telegram_id, bot_token, char_class=None, level: int = 1):
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}", char_class=char_class)
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    hero_id = resp.json()["id"]
    if level != 1:
        await set_hero_level(db_session, hero_id, level)
        await db_session.commit()
    return hero_id, headers


async def _make_node(db_session, enemy, region_code="r1", node_code="n1", node_type=CampaignNodeType.battle):
    region = await create_campaign_region(db_session, code=region_code)
    node = await create_campaign_node(db_session, region, code=node_code, node_type=node_type, enemy=enemy)
    await db_session.commit()
    return node


async def _start(client, headers, node_id):
    resp = await client.post("/api/v1/campaign/battles", headers=headers, json={"node_id": node_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _submit(client, headers, battle_id, round_number, action_type="basic_attack", skill_id=None):
    return await client.post(
        f"/api/v1/campaign/battles/{battle_id}/action",
        headers=headers,
        json={"round": round_number, "action_type": action_type, "skill_id": skill_id},
    )


# --- start / basic flow ------------------------------------------------------

async def test_start_campaign_battle_shows_enemy_intent_before_hero_acts(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Гоблин", level=1, hp=50, attack=10, defense=0, speed=5, crit_chance=0.0, reward_xp=15, reward_coins=10
    )
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40001, bot_token)

    body = await _start(client, headers, node.id)
    assert body["status"] == "running"
    assert body["current_round"] == 1
    assert body["enemy"]["intent"] is not None
    assert body["enemy"]["intent"]["skill_type"] == "damage"
    assert body["hero"]["current_hp"] == body["hero"]["max_hp"]


async def test_hero_below_enemy_level_can_still_attempt_the_node(client, db_session, bot_token):
    # Deliberately NO hero.level >= enemy.level gate (Stage 13 spec §1/§2)
    # — contrasts with PvE start_battle, which does gate on this.
    enemy = await create_enemy_template(db_session, name="Сильный враг", level=50, hp=10, attack=1, defense=0, speed=1, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40002, bot_token, level=1)

    body = await _start(client, headers, node.id)
    assert body["status"] == "running"


async def test_cannot_start_second_campaign_battle_while_one_is_running(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Враг", hp=999999, attack=0, defense=0, speed=1, crit_chance=0.0)
    node_a = await _make_node(db_session, enemy, node_code="na")
    node_b = await _make_node(db_session, enemy, region_code="r2", node_code="nb")
    _hero_id, headers = await _make_hero(client, db_session, 40003, bot_token)

    await _start(client, headers, node_a.id)
    resp = await client.post("/api/v1/campaign/battles", headers=headers, json={"node_id": node_b.id})
    assert resp.status_code == 409


# --- reward split -------------------------------------------------------------

async def test_first_clear_pays_full_reward_repeat_clear_pays_fraction(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Слабый враг", hp=1, attack=0, defense=0, speed=1, crit_chance=0.0, reward_xp=100, reward_coins=100
    )
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40004, bot_token)

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1)
    body = resp.json()
    assert body["status"] == "finished"
    assert body["result"] == "won"
    assert body["is_first_clear"] is True
    assert body["reward_xp"] == 100
    assert body["reward_coins"] == 100

    battle2 = await _start(client, headers, node.id)
    resp2 = await _submit(client, headers, battle2["id"], 1)
    body2 = resp2.json()
    assert body2["result"] == "won"
    assert body2["is_first_clear"] is False
    assert body2["reward_xp"] == 30  # REPEAT_CLEAR_REWARD_FRACTION = 0.3
    assert body2["reward_coins"] == 30


async def test_losing_grants_no_reward_but_still_appears_in_battle_history(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Убийца", hp=100000, attack=99999, defense=0, speed=99, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40005, bot_token)

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1)
    body = resp.json()
    assert body["result"] == "lost"
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0

    history = await client.get("/api/v1/battles", headers=headers)
    assert any(b["result"] == "lost" for b in history.json())


# --- non-reactive play: the two named examples from the spec -----------------

async def test_stunning_a_faster_hero_prevents_the_enemys_queued_heavy_strike(client, db_session, bot_token):
    warrior = await create_class(db_session, code="stun-cls", name="Stunner", base_speed=20, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Оглушитель", char_class=warrior)
    stun_skill = await create_skill_definition(
        db_session, warrior, code="stun_skill", skill_type=SkillType.stun, base_power=1, power_per_skill_level=0, cooldown_turns=0
    )
    await db_session.commit()

    enemy = await create_enemy_template(
        db_session, name="Орк", hp=100, attack=999, defense=0, speed=1, crit_chance=0.0, behavior_pattern=["heavy_strike"]
    )
    await create_enemy_ability(db_session, enemy, code="heavy_strike", name="Сокрушительный удар", skill_type=SkillType.damage, power=999)
    node = await _make_node(db_session, enemy)
    await db_session.commit()

    headers = telegram_headers(50001, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    hero_id = resp.json()["id"]
    resp = await client.post(f"/api/v1/heroes/me/skills/{stun_skill.id}/upgrade", headers=headers)
    assert resp.status_code == 200, resp.text

    battle = await _start(client, headers, node.id)
    assert battle["enemy"]["intent"]["ability_code"] == "heavy_strike"

    resp = await _submit(client, headers, battle["id"], 1, action_type="skill", skill_id=stun_skill.id)
    body = resp.json()
    assert body["hero"]["current_hp"] == body["hero"]["max_hp"], "Heavy Strike must not execute once the enemy is stunned"
    assert body["enemy"]["current_hp"] == body["enemy"]["max_hp"]
    assert any(e["action_type"] == "stunned" for e in body["log"])
    _ = hero_id


async def test_killing_a_low_hp_enemy_before_its_action_prevents_it(client, db_session, bot_token):
    warrior = await create_class(db_session, code="fast-cls", name="Fast", base_speed=20, base_attack=50, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Быстрый", char_class=warrior)
    await db_session.commit()

    enemy = await create_enemy_template(
        db_session, name="Раненый враг", hp=1, attack=999, defense=0, speed=1, crit_chance=0.0, behavior_pattern=["heavy_strike"]
    )
    await create_enemy_ability(db_session, enemy, code="heavy_strike", skill_type=SkillType.damage, power=999)
    node = await _make_node(db_session, enemy)
    await db_session.commit()

    headers = telegram_headers(50002, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    assert resp.status_code == 201

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1, action_type="basic_attack")
    body = resp.json()
    assert body["result"] == "won"
    assert body["hero"]["current_hp"] == body["hero"]["max_hp"], "the dead enemy's queued action must never execute"


# --- Defend --------------------------------------------------------------

async def test_defend_reduces_damage_even_against_a_faster_enemy(client, db_session, bot_token):
    defender = await create_class(db_session, code="def-cls", name="Defender", base_speed=1, base_defense=10, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Щитоносец", char_class=defender)
    await db_session.commit()

    enemy = await create_enemy_template(db_session, name="Быстрый враг", hp=1000, attack=30, defense=0, speed=20, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    await db_session.commit()

    headers = telegram_headers(50003, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    assert resp.status_code == 201

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1, action_type="defend")
    body = resp.json()
    # raw would be 30 - 10 = 20; Defend adds +50% of effective_defense (5) -> 30 - 15 = 15
    damage_taken = body["hero"]["max_hp"] - body["hero"]["current_hp"]
    assert damage_taken == 15
    assert any(e["action_type"] == "defend" for e in body["log"])


# --- Interrupt vs stun_immune boss -------------------------------------------

async def test_interrupt_skill_cancels_boss_intent_even_though_stun_would_fail(client, db_session, bot_token):
    warrior = await create_class(db_session, code="interrupt-cls", name="Interrupter", base_speed=20, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Прерыватель", char_class=warrior)
    interrupt_skill = await create_skill_definition(
        db_session, warrior, code="interrupt_skill", skill_type=SkillType.damage, base_power=5, power_per_skill_level=0,
        cooldown_turns=0, is_interrupt=True,
    )
    await db_session.commit()

    boss = await create_enemy_template(
        db_session, name="Босс", hp=500, attack=999, defense=0, speed=1, crit_chance=0.0, is_boss=True, stun_immune=True,
        behavior_pattern=["heavy_strike"],
    )
    await create_enemy_ability(db_session, boss, code="heavy_strike", skill_type=SkillType.damage, power=999)
    node = await _make_node(db_session, boss, node_type=CampaignNodeType.boss)
    await db_session.commit()

    headers = telegram_headers(50004, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    assert resp.status_code == 201
    resp = await client.post(f"/api/v1/heroes/me/skills/{interrupt_skill.id}/upgrade", headers=headers)
    assert resp.status_code == 200, resp.text

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1, action_type="skill", skill_id=interrupt_skill.id)
    body = resp.json()
    assert body["hero"]["current_hp"] == body["hero"]["max_hp"]
    assert any(e["action_type"] == "interrupted" for e in body["log"])


# --- Boss phases ---------------------------------------------------------

async def test_boss_phase_transition_is_logged_when_hp_crosses_the_threshold(client, db_session, bot_token):
    warrior = await create_class(db_session, code="phase-cls", name="PhaseTester", base_attack=60, base_speed=20, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Испытатель", char_class=warrior)
    await db_session.commit()

    boss = await create_enemy_template(
        db_session, name="Фазовый босс", hp=100, attack=0, defense=0, speed=1, crit_chance=0.0, is_boss=True,
    )
    await create_boss_phase(db_session, boss, phase_order=1, hp_threshold_pct=100)
    await create_boss_phase(
        db_session, boss, phase_order=2, hp_threshold_pct=50, attack_multiplier=2.0, transition_text="Босс приходит в ярость!"
    )
    node = await _make_node(db_session, boss, node_type=CampaignNodeType.boss)
    await db_session.commit()

    headers = telegram_headers(50005, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    assert resp.status_code == 201

    battle = await _start(client, headers, node.id)
    assert battle["enemy"]["phase_order"] == 1
    resp = await _submit(client, headers, battle["id"], 1, action_type="basic_attack")
    body = resp.json()
    assert body["enemy"]["current_hp"] == 40  # 100 - 60
    assert body["enemy"]["phase_order"] == 2
    assert any(
        e["action_type"] == "phase_transition" and e["status_effects"][0].get("text") == "Босс приходит в ярость!"
        for e in body["log"]
    )


# --- idempotency ---------------------------------------------------------

async def test_stale_round_retry_does_not_reapply(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Враг", hp=1000, attack=1, defense=0, speed=1, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40006, bot_token)

    battle = await _start(client, headers, node.id)
    first = await _submit(client, headers, battle["id"], 1)
    first_body = first.json()

    retry = await _submit(client, headers, battle["id"], 1)  # same round again, after it already resolved
    retry_body = retry.json()
    assert retry_body["current_round"] == first_body["current_round"]
    assert retry_body["enemy"]["current_hp"] == first_body["enemy"]["current_hp"]
    assert len(retry_body["log"]) == len(first_body["log"])


async def test_future_round_action_is_rejected(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Враг", hp=1000, attack=1, defense=0, speed=1, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    _hero_id, headers = await _make_hero(client, db_session, 40007, bot_token)

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 99)
    assert resp.status_code == 409


# --- item effects ----------------------------------------------------------

async def test_lifesteal_item_effect_heals_hero_on_hit_dealt(client, db_session, bot_token):
    warrior = await create_class(db_session, code="steal-cls", name="Vampiric", base_attack=40, base_hp=100, base_speed=20, base_crit_chance=0.0)
    hero_template = await create_hero_template(db_session, name="Вампир", char_class=warrior)
    await db_session.commit()

    weapon = await create_item_template(db_session)
    await create_item_effect(
        db_session, weapon, trigger=ItemEffectTrigger.on_hit_dealt, effect_type=ItemEffectType.lifesteal_pct, magnitude=50
    )
    enemy = await create_enemy_template(db_session, name="Враг", hp=1000, attack=20, defense=0, speed=1, crit_chance=0.0)
    node = await _make_node(db_session, enemy)
    await db_session.commit()

    headers = telegram_headers(50006, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template.id, "name": "Герой"})
    hero_id = resp.json()["id"]

    user = await get_user_by_telegram_id(db_session, 50006)
    user_item = await grant_item_to_user(db_session, user, weapon)
    await db_session.commit()
    await equip_item(db_session, hero_id, user_item.id)
    await db_session.commit()

    battle = await _start(client, headers, node.id)
    resp = await _submit(client, headers, battle["id"], 1, action_type="basic_attack")
    body = resp.json()
    # Hero acts first (speed 20 vs 1): deals 40-0=40 dmg, lifesteal heals 50%*40=20
    # (capped at max_hp, hero was already full). Enemy then hits back for
    # 20-10(default class defense)=10 -> net hp change is just that 10.
    assert body["hero"]["current_hp"] == body["hero"]["max_hp"] - 10
    assert any(e["action_type"] == "item_effect" for e in body["log"])


# --- campaign map ----------------------------------------------------------

async def test_campaign_map_availability_and_focus_node(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Враг", hp=1, attack=0, defense=0, speed=1, crit_chance=0.0)
    region = await create_campaign_region(db_session, code="map-region")
    node1 = await create_campaign_node(db_session, region, code="map-n1", enemy=enemy, depth=0, sort_order=1)
    node2 = await create_campaign_node(db_session, region, code="map-n2", enemy=enemy, depth=1, sort_order=1)
    await create_campaign_node_edge(db_session, node1, node2)
    await db_session.commit()

    _hero_id, headers = await _make_hero(client, db_session, 40008, bot_token)

    resp = await client.get("/api/v1/campaign/map", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    nodes_by_code = {n["code"]: n for r in body["regions"] for n in r["nodes"]}
    assert nodes_by_code["map-n1"]["available"] is True
    assert nodes_by_code["map-n2"]["available"] is False
    assert body["focus_node_id"] == node1.id

    battle = await _start(client, headers, node1.id)
    await _submit(client, headers, battle["id"], 1)

    resp2 = await client.get("/api/v1/campaign/map", headers=headers)
    body2 = resp2.json()
    nodes_by_code2 = {n["code"]: n for r in body2["regions"] for n in r["nodes"]}
    assert nodes_by_code2["map-n1"]["completed"] is True
    assert nodes_by_code2["map-n2"]["available"] is True
    assert body2["focus_node_id"] == node2.id
