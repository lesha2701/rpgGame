# RPG Backend — Architecture Notes

This is a separate FastAPI application from `../backend/` (the football-card
app this repo started as). It has its own database (`rpg_game`), its own
Alembic history, its own Docker service — see `../docker-compose.rpg.yml`
and `.env.rpg.example`. Nothing here is imported by or shared at runtime
with `../backend/` or `../bot/`.

This file tracks cross-cutting design decisions that aren't obvious from
the code alone. Update it whenever a stage introduces a decision future
stages need to know about.

## Database isolation (Stage 0)

- Own Postgres container (`rpg-postgres`), volume (`rpg_postgres_data`),
  network (`rpg_network`), credentials, and `RPG_DATABASE_URL` — deliberately
  a *different env var name* than the football app's `DATABASE_URL`, so it
  can never be picked up by accident even if both variables end up in the
  same shell/process environment.
- `app/config.py`'s `database_url` field has **no default** — a missing
  `RPG_DATABASE_URL` fails `Settings()` construction outright rather than
  silently falling back to anything.
- `app/core/db_guard.py::assert_not_football_database()` is a second,
  redundant check (called from both `app/main.py` and `alembic/env.py`)
  that refuses to start/migrate if the resolved URL contains `footycards`.
- Alembic history (`alembic/versions/`) starts at `0001` and shares nothing
  with the football app's `0001`-`0051` — never run football migrations
  against `rpg_game` or vice versa.

## Character foundation (Stage 1)

`Race` and `CharacterClass` are independent catalogs (not merged) — a
`HeroTemplate` combines a specific race + class + name (e.g. "Aldrik", Human
Warrior). `UserHero` is a player's owned instance: `level`, `xp`,
`hero_template_id`. V1 allows one *active* hero per user
(`User.active_hero_id`, enforced in `hero_service.create_hero`, not a DB
constraint) — deliberately not a hard schema limit, so multi-hero support
later doesn't need a migration.

Combat stats are never persisted on `UserHero` — always derived at read
time (`services/progression.compute_stats`) from the class's base stats +
per-level growth. See "Final hero stats" below for how Stage 4 extends this
same principle to equipment.

## Leveling (Stage 2)

- Level is a hard 1-100 range, enforced both in `apply_xp_gain()` (raises
  `ValueError` outside that range) and as a Postgres `CHECK` constraint on
  `user_heroes.level` (defense in depth).
- `xp` on `UserHero` is progress toward the *next* level, not a lifetime
  total. `apply_xp_gain()` carries any overflow past a level's threshold
  forward into the next level's progress — no XP is ever discarded except
  at the level-100 ceiling, where there's no level 101 to carry it toward.
- The curve itself lives in one place, `XpCurveConfig`
  (`services/progression.py`) — `xp_to_next_level(level) = round(base *
  level^exponent)`. Rebalance the whole curve by editing `DEFAULT_XP_CURVE`;
  nothing else needs to change.
- `visual_stage_for_level()`/`equipment_tier_for_level()` are pure functions
  of `level` (both use the same 10-level-band formula) — never a stored
  column. See "Item tiers" below — Stage 4 reuses
  `equipment_tier_for_level()` directly as the tier ceiling a hero can
  equip.

## Skills (Stage 3)

`SkillDefinition` belongs to a `CharacterClass` (shared by every hero of
that class); `CharacterSkill` is one hero's progress on one skill, created
lazily — a skill with no `CharacterSkill` row is simply "not learned yet"
(level 0 is never a stored value; the stored range is 1-10).

### Skill point budget is computed, not stored

Stage 3 explicitly avoided introducing a dedicated `skill_points` resource.
The rule:

```
total_skill_budget(hero.level)               # services/skill_progression.py
  = floor(hero.level * points_per_hero_level) # 1.0 by default -> 1 point/level

spent(hero)
  = sum(CharacterSkill.level for every skill the hero owns)

available(hero) = total_skill_budget(hero.level) - spent(hero)
```

Upgrading a skill (`skill_service.upgrade_skill`) costs `upgrade_cost(current_skill_level)`
points (flat 1 by default, configurable via `SkillUpgradeCostConfig`) and is
rejected with `InsufficientResourcesError` if `available < cost`. **Neither
number is persisted anywhere** — both are recomputed from `hero.level` and
the hero's existing `CharacterSkill` rows on every check, the same
derive-don't-store principle `compute_stats` already uses for combat stats.

This is *not* a currency: it has no balance column, can't be transferred,
gifted, or spent on anything except skill levels, and is entirely a
function of a hero's own level. **Coins remain the one real, spendable game
currency** (not yet implemented in this backend — see the football app's
`wallet_service.py` for the pattern this will eventually port) and are what
Stage 5's chests and future economy features will actually charge. Don't
conflate the two: "does this hero have enough skill points" and "does this
user have enough coins" are and will remain two unrelated checks.

Balancing the skill-point curve = edit `DEFAULT_SKILL_BUDGET` /
`DEFAULT_SKILL_UPGRADE_COST` in `services/skill_progression.py`; nothing
else needs to change.

## Equipment (Stage 4)

`ItemTemplate` (catalog: slot, tier 1-10, rarity) vs. `UserItem` (a player's
owned instance, nullable `equipped_hero_id`) — same template/instance split
as `HeroTemplate`/`UserHero`. Neither stat numbers nor `required_hero_level`
are stored on `ItemTemplate`: both are derived from `(slot, tier, rarity)`
by `services/item_progression.py` at read time, the same principle as
`compute_stats`/`xp_to_next_level`.

### Tier dominates rarity — the core balance rule

"A higher tier item is always stronger than a lower tier item, regardless
of rarity" (e.g. Common Tier 2 > Legendary Tier 1) is enforced
algebraically, not by hand-tuning each item:

```
tier_power(T)    = base_power * growth_per_tier ** (T - 1)      # growth_per_tier = 2.2
item_power(T, R) = tier_power(T) * RARITY_POWER_MULTIPLIER[R]   # common=1.0 .. legendary=1.75
affix_power(T)   = tier_power(T) * AFFIX_POWER_FRACTION          # 0.05, per affix
```

For the invariant to hold even in the worst case (max-rarity + max-affix-count
item at tier T vs. min-rarity + 0-affix item at tier T+1), `growth_per_tier`
must exceed `max(rarity multiplier) + max(affix count) * affix fraction`
(1.75 + 3*0.05 = 1.9 by default — `growth_per_tier=2.2` clears it with
margin). `item_progression.assert_tier_dominance_holds()` checks this
algebraically and is called from a test — a rebalance that violates the
invariant fails loudly instead of quietly shipping a broken item tier.

Rarity's other job — Common=0 affixes, Rare=1, Epic=2, Legendary=3
(`RARITY_AFFIX_COUNT`) — is why higher rarity still matters *within* a tier
without ever being allowed to beat the next tier.

### Slot stat weights, and why crit is excluded from items

Each `EquipmentSlot` has a fixed weight split (`SLOT_STAT_WEIGHTS`) across
4 additive stats — hp/attack/defense/speed — that always sums to 1.0, so an
item's full `item_power` always lands somewhere. `crit_chance`/`crit_damage`
are deliberately **not** itemized in V1: they're fractional/multiplier
values on a completely different numeric scale than the additive stats, and
the geometric tier curve built for hp/attack/defense/speed would need a
separate, heavily-dampened formula to make sense there. Crit stays a pure
class stat; itemized crit is a clean, isolated later addition.

### Final hero stats still aren't persisted

`hero_service.hero_to_out` composes `compute_stats(class, level)` +
the sum of every equipped `UserItem`'s computed stats, at read time, every
time. Equip/unequip never writes a stat anywhere — only which `UserItem`
rows have `equipped_hero_id` set. The combined total is rounded to `int`
exactly once, at the very end (`hero_to_out`) — item_power's tier/rarity
math is naturally fractional (geometric growth × weighted splits), so
rounding each item's contribution separately before summing would compound
error across up to 7 equipped items.

### One equipped item per slot, enforced at the DB level

`UserItem.slot` is a denormalized copy of `item_template.slot` (an item's
slot never changes after creation, so this can't drift) specifically so a
Postgres partial unique index — `(equipped_hero_id, slot) WHERE
equipped_hero_id IS NOT NULL` — can enforce "at most one equipped item per
slot per hero" without a join. `inventory_service.equip_item` auto-swaps:
equipping into an occupied slot silently unequips whatever was there first,
inside the same hero-row-locked transaction (`hero_service.lock_hero_for_update`,
reused verbatim from Stage 2/3 — the invariant being protected spans every
item that could occupy that slot, not just the one being equipped, so
concurrent equips into the same slot must serialize against each other
regardless of which `UserItem` row each targets).

### Alembic gotcha: reusing a Postgres ENUM type across migrations

`sa.Enum(..., name="x")` auto-creates its Postgres `TYPE` the first time a
column using it goes through `op.create_table()`. Reusing that type name in
a *second* `op.create_table()` — even with `create_type=False` on the Enum
object — can still raise `DuplicateObjectError`. Traced this to source
(`sqlalchemy.dialects.postgresql.named_types.NamedType._on_table_create`)
and confirmed empirically against a real Postgres instance:

- `create_type=False` **does** work when going through
  `Base.metadata.create_all()` (what the SQLite test suite uses) — that path
  passes `_is_metadata_operation=True`, which changes the gating condition.
- `create_type=False` **does not** reliably suppress creation when going
  through Alembic's `op.create_table()` directly — that path's own
  `_check_for_name_in_memos` bookkeeping is what actually prevents a
  duplicate, and it's scoped to *one migration's* DDL-runner session, not
  shared across separate migration files. 0004_equipment.py's
  `equipment_slot`/`item_templates`+`user_items` case only "worked" because
  both tables were created in the *same* migration (the second table's
  lookup hit that session's memo and skipped re-creating — nothing to do
  with `create_type` at all in hindsight).
- 0005_economy_and_chests.py needed to reference `item_rarity`, a type
  created back in 0004 — a genuinely different migration/DDL-runner session,
  so there's no memo to hit. The reliable fix there: add the enum-typed
  columns via raw `op.execute("ALTER TABLE ... ADD COLUMN ... item_rarity")`
  after `op.create_table()`, bypassing SQLAlchemy's Enum-DDL machinery
  entirely for just those columns. See that migration's module docstring
  for the full trace.

Rule of thumb: a brand-new enum type, used once, needs nothing special. The
same type reused by a second table *in the same migration* also needs
nothing special (the memo covers it). Referencing a type an *earlier*
migration already created always needs the raw-SQL `ADD COLUMN` workaround —
don't reach for `create_type=False` there, it won't help.

A related but distinct gotcha, hit in 0006 (Stage 6): **adding a new member
to an enum type an earlier migration already created** is not something
`op.create_table()` does for you at all — it only handles creating the type
the first time a column uses it, never extending one that already exists.
`TransactionType.battle_reward` was added to the Python enum in
`models/enums.py` but the live Postgres `transaction_type` type (created back
in 0005 with only `chest_purchase`/`admin_grant`) doesn't gain the new value
automatically; inserting a `CoinTransaction` with `type='battle_reward'`
fails with `InvalidTextRepresentationError` until something runs `ALTER TYPE
transaction_type ADD VALUE 'battle_reward'`. 0006 does this explicitly via
`op.execute(...)`, safe inside Alembic's transaction on Postgres 12+ as long
as the new value isn't *used* within that same transaction. There's no
`ALTER TYPE ... DROP VALUE` in Postgres, so 0006's `downgrade()` leaves the
added value in place rather than attempting a type rebuild.

## Economy and chests (Stage 5)

First full game loop: Coins → Chest → Item → Inventory → Equip → Stronger
Hero. Structurally adapted from the football app's wallet/Pack architecture
— see "Reused from FootballCards" in the Stage 5 report for the detailed
file-by-file breakdown; the summary that matters going forward:

- **Coins** (`User.balance`, `CoinTransaction`, `services/wallet_service.py`)
  are the one real spendable currency. `lock_user_for_update` moved here
  from `hero_service.py` (Stage 1-4 kept its own copy since coins didn't
  exist yet) — this is now the single canonical implementation, matching
  where the football app keeps it. **Never conflate this with Stage 3's
  skill-point budget** — that has no balance column and can't be spent on
  anything but skill levels; coins and skill points are two unrelated
  checks that happen to both gate a "can I afford this" question.
- **Chests** (`Chest`, `ChestRarityProbability`, `ChestOpening`,
  `services/chest_service.py`) are scoped to a Tier — `chest.tier` gates
  both which `ItemTemplate`s it can drop (`item_template.tier ==
  chest.tier`, never relaxed) and which heroes may open it at all
  (`hero.level >= required_level_for_tier(chest.tier)` — the *same*
  function Stage 4 uses to gate equipping, not a second copy of that
  formula). One chest grants exactly one item in V1 (no
  `PackOpeningCard`-style join table needed).
- **Idempotency** is the exact two-layer football pattern: an early lookup
  by `(user_id, idempotency_key)` before doing anything, plus a DB unique
  constraint (`uq_chest_opening_idem`) as the real guarantee, with a
  commit-time `IntegrityError` catch that re-queries and returns the
  race-winner's result instead of erroring.
- **Admin auth** (`is_admin`, `core/security.create_admin_token`/
  `decode_admin_token`, `core/dependencies.get_current_admin`) was deferred
  in Stage 1 (no admin panel yet) and ported in now, needed for Stage 5's
  admin chest CRUD. Same shape as the football app's: a bearer JWT minted at
  `/auth/session`, re-checked against `settings.admin_ids` on every request
  (not just trusted from the token/column) so revoking someone from
  `RPG_ADMIN_TELEGRAM_IDS` invalidates already-issued tokens.
- Admin CRUD (`routers/admin_chests.py`) intentionally skips three things
  the football app's `admin_packs.py` has: image upload (no static-asset
  serving in this backend yet), the `AdminAction` audit log, and the
  Monte-Carlo probability preview endpoint. All three are additive — Stage
  13 (the dedicated admin-panel stage) is the right place to port them, not
  a reason to block Stage 5's core loop.

## PvE battle engine (Stage 6)

First full combat loop: Hero → Stats → Skills → Equipment → Battle → XP +
Coins → further hero growth. One hero vs. one enemy, resolved entirely
within a single request — there is no multi-request battle session anywhere
in this stage.

### Why no BattleSession / EnemyInstance

Every earlier stage that models something ongoing (a chest opening, an
equip) either completes in one DB transaction or persists a durable state
blob (`GameSession`/`TacticoMatch`'s `server_state`, per the football app's
pattern this project already knows). PvE combat here has no reason to be
either: a fight is small (≤30 rounds, deterministic once the RNG seed and
inputs are fixed), server-authoritative from end to end (nothing the client
sends affects the outcome except *which* enemy to fight), and there is no
"come back later and resume" requirement anywhere in the Stage 6 brief. So:

- **No `BattleSession`/`RUNNING` state.** `simulate_battle` runs the whole
  fight synchronously inside `battle_service.start_battle` and only the
  finished result is ever persisted (`Battle`, an immutable record — no
  `updated_at`, matching `ChestOpening`'s precedent). `BattleResult` is
  deliberately a 2-value enum (`won`/`lost`); there's no "in progress" value
  to store because nothing is ever in progress across requests.
- **No `EnemyInstance`.** `EnemyTemplate` rows are stat blocks, not
  per-fight entities — nothing about a Goblin's stats varies per encounter
  in V1, so instantiating one per battle would be a table with no
  information the template doesn't already have. If PvP or enemy-affix
  variance ever gets added, that's the natural point to introduce one; V1
  doesn't need it.
- **No enemy skills / `EnemyTemplateSkill` join table.** Enemies always
  Basic Attack (`battle_engine.py`'s module docstring). This was the
  simplest option that still makes hero skill choice matter (the hero's kit
  is the entire tactical layer in V1).

### Two-layer split, enforced by import direction

- **`services/battle_engine.py`** — pure Python: `CombatantStats` +
  `BattleSkill` (already-computed inputs) in, `BattleOutcome` (won/turns/
  structured log) out. No DB session, no FastAPI, no commit, and critically
  **no injected global randomness** — every random decision (crit rolls)
  goes through a `random.Random` instance the caller supplies, so identical
  inputs + identical seed reproduce an identical log byte-for-byte
  (`tests/test_battle_engine.py::test_same_seed_and_inputs_reproduce_the_exact_same_battle_log`).
  `battle_service.py` itself calls `simulate_battle(..., random.Random())`
  with a fresh, unseeded instance per real battle — determinism is a
  property of the engine, not a promise that real battles are predictable.
- **`services/battle_service.py`** — the only place that touches the DB.
  Loads the hero's *real* computed stats via `hero_service.hero_to_out`
  (the exact function `/heroes/me` calls) rather than a second, parallel
  stats computation, so battle math can never drift from what the player
  sees as their stats. Loads learned skills via `skill_service.get_hero_skills`
  + `skill_progression.power_at_level` (same formula the skill-upgrade
  endpoints use). Owns the whole transaction: simulate, then (if won) fold
  `hero_service.grant_xp` + `wallet_service.credit_coins` + the `Battle`
  insert into one `db.commit()`.

### `grant_xp` becomes commit-free (retrofit to Stage 2)

Before Stage 6, `hero_service.grant_xp` committed and re-fetched internally
— fine when it was the last thing a request did, wrong once a request needs
to compose it with other mutations that must all-or-nothing together. It now
only locks the hero row and mutates it in memory, exactly like
`wallet_service.credit_coins`/`debit_coins` already did; the caller commits
once after every mutation for the operation is applied. `battle_service.
start_battle` is the first caller that actually needed this: XP, coins, and
the `Battle` row must land together or not at all, and a battle that crashed
after granting XP but before saving the fight would be a duplicate-reward
bug wearing a trenchcoat. Every existing Stage 2 caller of `grant_xp`
(the test suite's direct calls) was adapted to commit explicitly — no
production caller changed behavior, since `hero_service.create_hero` and
`skill_service.upgrade_skill` already manage their own commits around the
functions they call.

### Damage formula and turn structure

One formula (`battle_engine.compute_basic_damage`), reused identically for
basic attacks and `damage`-type skills (a skill just substitutes its power
for attack): `max(1, attack - defense)`, ×`crit_damage` on a crit roll
against `crit_chance`. Speed decides turn order only (round-based: faster
combatant acts, then the other, hero wins ties) — it never enters the damage
number itself. Of `SkillType`'s values, Stage 6 implements `damage`/
`shield`/`buff`/`dot`/`stun`; `heal`/`debuff` are out of scope (not in the
brief, no seeded skill uses either) — a hero holding one simply never
selects it, same effect as it always being on cooldown. Skill AI is
deliberately simple: first ready skill by `sort_order`, else Basic Attack —
no target selection logic beyond the type-implied default (damage/dot/stun
target the enemy, shield/buff target self).

A round-cap stalemate (30 rounds, nobody dead) resolves by remaining HP%,
hero winning ties — same tie-break convention used for equal-speed turn
order, kept consistent so "hero wins ties" means one thing throughout the
engine, not two similar-but-different rules.

### Structured JSON battle log

`Battle.log` is a JSON array of entries (`turn`, `attacker`, `target`,
`action_type`, `skill_id`, `damage`, `critical`, `target_hp_after`,
`status_effects`), not a text blob — built for a future frontend to animate
turn-by-turn, matching the "derive/store what a client can render" spirit of
`visual_stage`/tier elsewhere in this project. Stored once at battle
creation and never recomputed — `GET /battles/{id}` and idempotent replays
return the exact same log that was simulated, not a re-simulation (`battle`
is immutable; only the *hero_level/hero_xp/balance* fields in the response
are live, re-read from the current hero/user each time, same as
`chest_service` always returning the current balance rather than a stored
one).

### A concurrency bug live Postgres testing caught (and SQLite couldn't)

`start_battle`'s idempotency-race fallback (`IntegrityError` → `rollback()`
→ re-fetch the winner's row) originally accessed `hero.id`/`user.id`
directly after the rollback. That crashed with `sqlalchemy.exc.
MissingGreenlet` under a **genuine** concurrent race against real Postgres:
`Session.rollback()` expires every attribute SQLAlchemy was tracking on
every object in the session — including primary keys, not just the columns
this request had mutated — and touching an expired attribute synchronously
(without an `await`ed refresh first) can't run the implicit reload inside
async SQLAlchemy's greenlet machinery. SQLite's shared-StaticPool test
connection never manufactures a real `IntegrityError` race in the first
place (documented on every skipped concurrency test in this project), so
this path is structurally untestable in the unit suite — it was only found
by literally running two concurrent `POST /battles` requests with the same
idempotency key against `rpg-postgres` and reading the traceback. Fixed by
capturing `user_id`/`hero_id` as plain ints at the top of `start_battle`,
before any commit/rollback can happen, and never touching the ORM objects'
attributes again after a rollback (fresh `db.get()` calls only). Re-verified
live afterward: 4 more concurrent-pair runs, each landing on exactly one
`Battle` row and exactly one coin credit.

### Scope explicitly not built in Stage 6

PvP/matchmaking/ratings/guilds, enemy skills, heal/debuff skill types,
`BattleSession`/any resumable multi-request battle state, frontend/
animations, equipment durability, and HP persisting between battles (every
battle starts the hero at full computed HP — there is no stored "current
HP" column anywhere on `UserHero`). All of these were explicit exclusions in
the brief, not oversights.

## Expeditions (Stage 7)

A hero commits to an expedition for a fixed duration; the player claims a
fixed XP+coins reward once it's done. The entire stage's constraint: **no
background worker** (no Celery/Redis/APScheduler, no scheduled task of any
kind) — every check is a pure comparison against a timestamp already
written to the row, so a server that was down for the whole duration still
resolves `claim()` correctly the instant it comes back.

### Reused from FootballCards: `free_pack_service._is_available()`

The football app already solved "is this timestamp-gated thing available
yet, without a scheduler" for the free-pack cooldown:
`user.free_pack_available_at` is a stored deadline, and availability is
`ensure_aware(available_at) <= datetime.now(timezone.utc)` — nothing else.
`expedition_service._is_time_complete()` is structurally the same function,
just checking `UserExpedition.completed_at` instead of a per-user cooldown
column. `ensure_aware()` itself is ported near-verbatim into this backend's
new `app/core/timeutil.py` — SQLite (the test suite) hands back naive
datetimes for `DateTime(timezone=True)` columns, Postgres doesn't, and every
naive datetime in this codebase is UTC by convention, so treating naive as
UTC keeps the comparison correct on both.

**Reimagined, not reused:** the football app's other "wait, then get
something" mechanics (`TacticoMatch`/`GameSession`'s `server_state` blob,
resolved lazily by a sweep function whenever either player's client polls)
solve a different problem — an *interactive*, multi-party state machine
that can branch depending on what a player does mid-flight. An expedition
has exactly one branch (nothing happens during it) and one party (the hero
who started it), so there's nothing to sweep and nothing that needs
resolving opportunistically on someone else's request — the free-pack
timestamp-comparison shape is the right-sized reference, not Tactico's.

### Why `status` only ever stores 2 values, not 3

The brief's `UserExpedition.status` lists `RUNNING`/`COMPLETED`/`CLAIMED`,
but nothing is ever allowed to *write* `COMPLETED` — that would need
something to perform the transition, i.e. the background job this stage
explicitly must not have. `ExpeditionStatus` (`app/models/enums.py`) is a
2-value enum, `running`/`claimed`; `expedition_service._status_out()`
computes the third, client-facing label at read time: `"claimed"` if the
stored status says so, else `"completed"` if `now() >= completed_at`, else
`"running"`. Same "derive, don't store" call as `BattleResult` choosing not
to store a pending/draw value (Stage 6) — the API still speaks all three
words, the database only ever holds the two that something actually writes.

### `completed_at`/`reward_xp`/`reward_coins` are snapshotted at `start()`, not read live at `claim()`

All three are copied from the template onto the `UserExpedition` row the
moment it's created, not re-read from `ExpeditionTemplate` when checking
completion or granting the reward. Two reasons: (1) it freezes the terms a
player already committed to — an admin rebalancing a template's duration or
reward mid-flight must not retroactively change an expedition already
running, the same "commit to fixed terms upfront" fairness call as
`ChestOpening.price_paid` snapshotting the price paid rather than joining
the (possibly since-repriced) `Chest`; (2) it means `claim()` never needs to
touch `ExpeditionTemplate` at all — completion is a comparison against this
row alone.

### Busy check: only expeditions, not battles — and why that's not a gap

The brief asks for "hero isn't already on an expedition, and isn't
mid-battle." Only the first half needed a query: `Battle` rows in this
backend are never created until fully resolved (Stage 6 — no
`BattleSession`, nothing persists mid-fight), so there is no in-progress
battle state anywhere a hero could be "caught in" across requests. The
mid-battle half of the check is vacuously true given how Stage 6 was built,
not a gap Stage 7 left open — see `start_expedition`'s comment on the check
it does still perform. Stage 7 deliberately does **not** introduce a
general-purpose "busy" system (a shared `UserHero.busy_until`/status column
every future occupying activity would read and write) — the brief was
explicit that nothing yet needs one, and the one check that does exist lives
entirely in `expedition_service.py`. If a third occupying activity shows up
later needing the same exclusion, that's the point to generalize; two
special cases (one real, one vacuous) isn't it yet.

### Concurrency: two different mechanisms for two different races

- **Starting** a second expedition while one is running: the primary
  mechanism is locking the hero row (`hero_service.lock_hero_for_update`)
  *before* checking for an existing running expedition and inserting the
  new one — same "lock first, so check-then-act is atomic" pattern as Stage
  4's equip-into-a-slot. A partial unique index
  (`user_expeditions(hero_id) WHERE status='running'`) backs this up at the
  DB level as defense in depth, the same two-layer shape as Stage 4's
  one-equipped-item-per-slot index. Verified live against `rpg-postgres`
  (two concurrent `start()` calls for the same hero, different template
  ids): exactly one succeeds, the loser gets a clean `ConflictError`, and
  exactly one `running` row exists afterward — reproduced across 2 runs.
- **Claiming** the same `UserExpedition` twice concurrently doesn't need an
  idempotency-key/unique-constraint dance at all, unlike chest/battle
  *creation* — `claim()` operates on a row that already exists and already
  has an id, so locking that one row (`SELECT ... FOR UPDATE`, scoped with
  `of=UserExpedition` since `expedition_template` is `lazy="joined"` — the
  same outer-join gotcha `lock_hero_for_update` already documents) and
  re-checking its status *after* acquiring the lock is sufficient: Postgres
  serializes the two transactions on that lock, and whichever acquires it
  second sees `status=claimed` already (the first committed before
  releasing it) and returns that result granting nothing further. Verified
  live: two concurrent `claim()` calls on the same id, exactly one balance
  credit — reproduced across 2 runs. Learned from Stage 6's `MissingGreenlet`
  bug ahead of time: neither concurrency path here ever calls
  `db.rollback()`, so there's no expired-attribute footgun to fall into in
  the first place (claim's only failure mode, "not completed yet", is
  raised *before* any mutation happens, needing no rollback at all).

### Scope explicitly not built in Stage 7

Celery/Redis/APScheduler/any background worker, push/Telegram notifications
when an expedition completes, randomized rewards, item rewards, PvP,
multiple concurrent expeditions per hero, a general-purpose busy/occupied
system, and frontend. All explicit exclusions in the brief, not oversights.

## Quest system, and two prep refactors (Stage 8)

Before Quest System itself, two small extractions the Stage 7 audit
flagged were done first — both are pure refactors, no API behavior change
(full pre-existing test suite passes unchanged, same count, before and
after).

### `reward_service.grant_hero_reward` — the third caller was the tell

`battle_service.start_battle` and `expedition_service.claim_expedition`
each independently implemented "lock the user row, grant_xp, credit_coins"
with only the `TransactionType`/description/related_object differing.
Quest claims needed the exact same sequence a third time — which is what
made it worth extracting rather than writing a fourth near-copy.
`services/reward_service.py`'s `grant_hero_reward()` is the one place that
sequence lives now; all three callers (Battle, Expedition, Quest) go
through it. It invents no new formula (still just `hero_service.grant_xp`
+ `wallet_service.credit_coins`, unchanged), preserves the exact lock order
every caller already used by convention (user, then hero via `grant_xp`'s
own internal `lock_hero_for_update`), and never commits — transactionally
composable by the same contract `grant_xp`/`credit_coins` already follow,
so each caller still folds it into its own single commit (the `Battle`
insert, `UserExpedition.claimed_at`, `UserQuest.claimed_at`).

### `HeroProgressOut` — shared computation, not a shared response shape

`BattleOut`/`UserExpeditionOut` each built an identical "current
level/xp/balance" block by hand. `hero_service.hero_progress_out(hero,
user)` is now the one function that computes it. Existing responses were
**not** restructured to nest this — `BattleOut.hero_level`/`hero_xp`/
`balance` and `UserExpeditionOut`'s equivalents keep their already-shipped
flat field names, just now populated by pulling fields off the shared
object rather than computing them inline. Changing either response's shape
would have been unnecessary churn for zero functional gain (no frontend
consumes these yet, but the fields are already a settled contract).
`QuestClaimOut` — a brand-new response with no legacy shape to preserve —
nests `HeroProgressOut` directly under `hero_progress`, which is what a new
endpoint gets to do that the old ones didn't.

### Quest System: reads only, never coupled into Battle/Expedition/Chest

`QuestDefinition` (catalog) / `UserQuest` (claim-only state: `claimed_at`
nullable, nothing else) — the split is now familiar from every earlier
catalog/instance pair. The one genuinely new rule: **`UserQuest` has no
progress column, and nothing computes progress except by querying
Battle/UserExpedition/ChestOpening/UserHero/UserItem/CharacterSkill
directly** (`services/quest_progression.py`). Those five tables/services
never import or reference quests at all — the dependency arrow points one
way, from quest code reading their tables, never the reverse. This was the
explicit design goal: adding an entire new game system without touching a
single line of Battle/Expedition/Chest/skill code, and without an event bus
to wire them together. Proven live, not just in theory: the dev-mode hero
used for every prior stage's manual verification already had 8 battle
wins, 3 claimed expeditions, 2 opened chests, and 4 skill upgrades from
*before Quest System existed* — the very first `GET /quests` call showed
correct, non-zero progress on all of them, computed purely by counting
rows that were already there.

`QuestConditionType` covers 6 values for V1 (`battles_won`,
`expeditions_claimed`, `chests_opened`, `hero_level`, `items_equipped`,
`skills_upgraded`) — 4 are lifetime cumulative counts, 2
(`hero_level`/`items_equipped`) are current-state snapshots that could in
principle decrease; both kinds are computed identically (one live query,
at read/claim time), so nothing in quest_progression.py special-cases
which kind a condition is. `skills_upgraded` sums `CharacterSkill.level`
across a hero's learned skills rather than counting distinct skills
learned — a class only ever has 3 skills (Stage 3), so "5 distinct skills"
could never be satisfied; the sum is exactly the lifetime count of
`upgrade_skill` calls, since `CharacterSkill.level` only ever increases.

Every active `QuestDefinition` is created as a `UserQuest` row for a user
all at once, the first time `GET /quests` is called for them
(`quest_service._ensure_user_quests`) — not lazily per-quest, and
deliberately **not** the football app's slot-rotation/metric-baseline
system (`task_service._ensure_slots_filled`, `metric_baseline`
snapshotting). V1 has no limited "visible slots" to rotate through:
everything active is always visible to everyone. `GET /quests` does not
require an active hero (hero-scoped condition types just show progress 0
without one — see `quest_progression.get_quest_progress`'s hero=None
handling); claiming does, since the reward always includes XP.

### Claim semantics differ from Expedition on purpose

Expedition's `claim()` treats a repeat call as an idempotent replay
(returns 200, same result, no double grant). Quest's `claim()` treats a
repeat call as a 409 (`"Reward for this quest has already been claimed"`)
— matching the football app's `claim_task_reward`, which also errors on an
already-claimed task rather than re-confirming it. Both are safe under
real concurrency via the identical mechanism (lock the one row by its own
id, re-check state after the lock, no idempotency-key needed since neither
operates on a fresh create) — they just differ in what the *loser* of a
legitimate double-click sees, and that's a deliberate per-feature choice,
not an inconsistency to fix later.

### `quest_reward` and the now-familiar enum gotcha — applied proactively this time

`TransactionType.quest_reward` needed the same `ALTER TYPE ... ADD VALUE`
treatment as `battle_reward` (Stage 6) and `expedition_reward` (Stage 7) —
`op.create_table()` never extends an existing enum type, only creates one
the first time it's used. Unlike the previous two times, this was written
into `0008_quests.py` from the start rather than discovered live against
Postgres after a 500 — the documented rule of thumb held on the first try.

### Scope explicitly not built in Stage 8

Event bus/message broker of any kind, Celery/Redis/background workers, a
`QuestProgress` table, a `progress` column on `UserQuest`, any change to
Battle/Expedition/Chest's API or internals, frontend, PvP, daily rewards,
referrals, a general achievement system, slot rotation, and item/chest
rewards (Quest rewards are XP + coins only, same restraint as Expedition's
V1 scope). All explicit exclusions in the brief, not oversights.

## Arena / PvP (Stage 9)

Two players, one hero each, turn-based combat over many HTTP requests
instead of one. The one new architectural question every earlier stage
didn't have to answer: two humans acting independently, between requests,
with no background process to coordinate them.

### `battle_engine.py` gained a public API, not a second engine

PvE's `simulate_battle` picks each action automatically (`_pick_ready_skill`)
and resolves an entire fight in one call. PvP needs the same damage/skill/
cooldown/buff/dot/stun mechanics, but the ACTION comes from a player's HTTP
request instead of AI, and must be applied one round at a time, persisted
between requests. Rather than a second, duplicate `pvp_engine.py`,
`battle_engine.py` was refactored (Pyright/no-behavior-change verified: the
full pre-existing `test_battle_engine.py` suite passes unchanged, same 15
tests, before and after) to expose the building blocks it was already
internally built from:

- `CombatantState` (was `_CombatantState`) — the mutable per-side runtime
  state (HP/cooldowns/buffs/shield/dot/stun). Gained `combatant_state_from_
  dict()` for round-tripping through JSON — the one thing PvE never needed
  (a whole fight lives in memory for one function call; PvP's state has to
  survive between two players' separate requests).
- `tick_start_of_turn` (was `_tick_start_of_turn`) — cooldown/buff/DoT
  ticking, unchanged.
- `apply_action(actor, actor_name, action, target, ...)` — new. Extracted
  from the second half of `_take_turn`: applies ONE already-chosen action
  (`None` = Basic Attack, a `BattleSkill` = use it). `_take_turn` (PvE)
  now calls `_pick_ready_skill()` then delegates to this; `arena_service.py`
  calls it with a player-submitted choice instead. `_apply_skill`/
  `_apply_shield`/`_pick_ready_skill` stay private — implementation details
  of `apply_action`, not something either caller needs directly.

`battle_service.py`'s `_hero_combat_stats`/`_hero_battle_skills` were
similarly promoted to public (`hero_combat_stats`/`hero_battle_skills`) so
`arena_service.py` builds its match-start snapshot from the exact same
functions PvE uses — not a parallel computation.

### One table, stateful then frozen — same shape as UserExpedition, not Battle

`ArenaMatch` is mutable while `status=running`, then nothing ever writes to
it again once `status=finished` — the same row serves as both live match
state and its own history record (`GET /arena/matches` just lists them,
same as `UserExpedition.list_history`). No separate `ArenaMatchResult`.
Structurally this is much closer to `UserExpedition` (spans real time,
mutates in place, then freezes) than to `Battle` (created already resolved
in one insert) — PvP simply can't be a one-shot insert the way PvE is,
because a human has to choose each side's actions across separate requests.

`ArenaMatchStatus` is 2 values (`running`/`finished`), same reasoning as
`BattleResult`/`ExpeditionStatus`/`QuestConditionType` before it: V1 has no
accept-flow or matchmaking (a challenge immediately creates a running
match — see below), so there's no third "pending" state a background job
would need to advance.

### `state` (JSON): the one thing that's genuinely stateful, nothing more

Per side: the frozen combat-input snapshot (`stats` + `skills`, copied via
`hero_combat_stats`/`hero_battle_skills` ONCE at match creation and never
re-read), the mutable `CombatantState` (HP/cooldowns/buffs/etc, serialized
via `dataclasses.asdict`/`combatant_state_from_dict`), and the current
round's `pending_action` (`null` until that side submits). Same precedent
as `Battle.log` already being JSON in this codebase — not a football
import. No `player_a_last_acted_round`/`player_b_last_acted_round` columns
(see the idempotency section below for why those turned out to be
unnecessary, not just omitted for simplicity).

### Snapshot invariance — the property Stage 9's brief was most worried about

A hero's stats/skills are captured **once**, at match creation, and never
read from the live `UserHero`/`UserItem`/`CharacterSkill` rows again for
the rest of that match. Equipping different gear, leveling up, or learning
a new skill mid-match has zero effect on an already-running fight — proven
live: a hero's level was bumped from 4 to 20 via a direct `UPDATE`
mid-match (live attack 26 → 50), and the next combat exchange in that match
still dealt the damage the ORIGINAL snapshot (attack=26) implied, not the
live value. `test_snapshot_is_frozen_at_match_creation_equipment_change_
has_no_effect` covers the same property (equip + level-up) in the test
suite. HP itself lives only in `state`, never on `UserHero` — same rule
Stage 6 already established for PvE ("no stored current HP column
anywhere on UserHero"), just reaffirmed here rather than reopened.

### Turn flow: whoever submits second resolves the round, in that request

`POST .../action` records the submitter's `pending_action`. If the other
side already has one recorded, the round resolves immediately, in that
same request — no separate `.../resolve` endpoint. This is the football
app's `tactico_service.submit_round` shape (see the comparison below),
applied without its slot/queue complexity: reuses `tick_start_of_turn` +
`apply_action` in speed order (same convention as PvE — faster combatant
acts first, `player_a` wins ties), checks the win condition (either side's
HP ≤ 0, or a round-cap stalemate), grants the reward via `reward_service.
grant_hero_reward` exactly once (from the single call site that actually
flips `status` to `finished`), and commits everything together.

**Stun**, unlike the original design proposal, does NOT let the server skip
waiting for a stunned side's submission — both sides still submit every
round (simpler client contract, no branching on "do I need to act this
round"); a stunned side's submitted action is simply discarded during
resolution and replaced with a `"stunned"` log entry, exactly like PvE.

**Skill cooldown validation happens at resolution, not submission** — a
subtlety worth documenting because it's easy to get backwards: checking
cooldown readiness when a player submits (against the stored, not-yet-
ticked-for-this-round value) would be systematically one round stale
compared to what PvE checks (post-tick, at the start of the actor's turn).
Submission only validates that the hero actually knows the skill; if it
turns out not to be ready by the time resolution's own `tick_start_of_turn`
runs, the chosen skill silently falls back to Basic Attack — the same
tolerance PvE's AI already has when nothing it wants is off cooldown, just
triggered by a stale human choice instead of an empty AI choice-set.

### Idempotency: fixing a real gap found during design review, not just documenting one

The original design proposed `player_a_last_acted_round`/`player_b_last_
acted_round` columns, compared against `current_round`. Working through
the brief's own retry-after-resolve scenario (A and B both act, the round
resolves, B's client times out before seeing the response, B retries the
identical request) found a genuine bug in that design: by the time the
retry arrives, `current_round` has already advanced past what `last_acted_
round` recorded, so the comparison `last_acted_round >= current_round`
no longer catches the retry as stale — it would have been silently treated
as a fresh action for the NEW round instead. Fixed by dropping those
columns entirely and instead requiring the client to echo back the round
number it believes it's acting on (`ArenaActionRequest.round`, learned from
the match-creation/previous-action response), compared against the
server's authoritative `current_round`:

- `round < current_round` → the round already resolved; return current
  state, no mutation. Catches the exact retry-after-resolve scenario.
- `round == current_round` and this side's `pending_action` is already
  set → duplicate submission before resolution; return current state, no
  mutation.
- `round == current_round` and nothing pending yet → normal path.
- `round > current_round` → reject (client is out of sync with the match).

No `idempotency_key` needed anywhere in Arena — every operation targets a
row (and, for actions, a round) that already has an identity, the same
reasoning Expedition/Quest claims already established for "this isn't a
fresh create, it's a state check on something identified by its own id."
Verified live against `rpg-postgres`: concurrent duplicate submissions from
the same player (idempotent replay, no double damage), concurrent
submissions from both players for the same round (exactly one resolution),
and — the highest-stakes case — concurrent submissions of the round that
finishes the match (reward credited exactly once, confirmed via wallet
balance before/after).

### Reused from FootballCards: `tactico_service.py`, with one deliberate divergence

`TacticoMatch`'s shape (`server_state` JSON, `status`, `resolved_at`/
`expires_at`) is `ArenaMatch`'s direct ancestor. `submit_round`'s "record
my pick, resolve now if the other side already has theirs" is `submit_
action`'s ancestor. `_auto_play_overdue_rounds` (a lazy sweep run at the
top of `list_matches`/`get_match`, never a background job) is `_apply_
sweep_if_overdue`'s ancestor — Arena's version defaults the AFK side to
Basic Attack (deterministic, matching PvE AI's own fallback) rather than
Tactico's random card pick, since this game has a well-defined "do nothing
clever" action and football's card game doesn't. `_has_active_match`
(one active match per user) is why `ArenaMatch` enforces one running match
per HERO the same way, both via a lock-based primary mechanism and a
partial-unique-index backup.

**Deliberate divergence:** Tactico's `_record_pick` rejects a same-round
duplicate submission with a 409 ("you already submitted a card"). Arena
instead treats it as an idempotent replay (see above) — the brief's own
retry-after-timeout scenario needed genuine idempotency, not a clean error,
matching how chest/battle/expedition/quest already treat a plausible retry
as a replay rather than a client mistake.

**Not reused:** `TacticoQueueEntry` (matchmaking) and `match_service.py`
entirely — the latter is a solo player reacting to a pre-generated "moment
queue" against a synthesized bot, not two synchronized human players; the
only thing it shares with Arena is the same `_lock_match`-then-mutate-JSON
shape every other stateful table in this codebase already uses.

### Two-hero locking: extending Stage 7's single-hero pattern, not inventing a new one

`create_match` locks BOTH participants' hero rows, sorted by id (same
deadlock-avoidance shape as the football app's sorted (claimant, referrer)
pre-lock in `free_pack_service.claim_free_pack`), before checking whether
either already has a running match. This is the PRIMARY correctness
mechanism; the two partial unique indexes on `ArenaMatch` (`player_a_hero_
id`/`player_b_hero_id`, each `WHERE status='running'`) are defense in
depth, and — documented honestly rather than oversold — don't by
themselves prevent a hero being `player_a` in one running match and
`player_b` in another; only the lock-based check does.

### Reward numbers: plain constants, not a new config-table pattern

`ARENA_WIN_REWARD_XP`/`ARENA_WIN_REWARD_COINS` are module-level constants
in `arena_service.py`, not a database row. Enemy/Expedition/Quest rewards
each live on that feature's own catalog row because each of those has a
natural per-template home for the number; Arena has no such row (every
match is an arbitrary pair of heroes, not a selection from a template), so
these follow the OTHER existing precedent in this codebase instead —
`battle_engine.MAX_ROUNDS`/`BUFF_DURATION_TURNS`, `progression.
XpCurveConfig` — tuning constants centralized in the module that uses them,
not scattered inline, but not a persisted config table either until a
genuine need for one appears (see the Stage 8 audit's `GameConfig`
discussion).

### Scope explicitly not built in Stage 9

Matchmaking, MMR/rating, seasons, leagues, an accept/decline challenge flow
(V1 challenges start the match immediately), a general-purpose busy system
spanning Expedition/Battle/Arena (snapshotting already makes a hero's stats
immune to what it's doing elsewhere; only one-Arena-match-at-a-time is
enforced), admin panel, and frontend. All explicit exclusions in the brief,
not oversights.

## Referrals + Free Chest (Stage 10)

Two independent features, both landing with **zero new tables**. The
whole stage's discipline was making sure of that before writing anything —
both designs turned out to already be representable by existing rows plus,
at most, two new columns.

### Referrals: the link is 2 columns on `User`, not a table

`User.referred_by_id` (self-FK) + `User.referral_reward_granted` (bool) —
no `Referral` table, no `ReferralCode` table. There is nothing to
normalize out of "who invited whom" beyond one nullable pointer, and
nothing to normalize out of "has the one-time reward for this link already
fired" beyond one boolean. `referral_count` is deliberately **not** a
column — `referral_service.referral_count()` is a `COUNT(User WHERE
referred_by_id = X AND referral_reward_granted)`, the same "derive an
aggregate from existing rows" call Stage 8's Quest condition types already
made, applied here to a self-join instead of a cross-table count.

**Referral code** is `str(user.telegram_id)` — nothing generated, nothing
stored, ported directly from the football app's own `X-Referral-Code`
mechanism (`core/dependencies.py`, both apps). The link is captured exactly
once, in the `if user is None:` (fresh-insert) branch of `_get_or_create_
user` — RPG already had this function, including its SAVEPOINT-based
concurrent-first-request handling, ported from football in an earlier
stage; Stage 10 only added an `else:` clause to the existing `try/except
IntegrityError`, mirroring exactly how football's own version structures
it, so the referral capture only ever runs on the winning insert, never on
a race-loser's fallback fetch or on any later "existing user" update path.
That's what makes the link immutable after creation — there's no runtime
"already set" guard because the code that could change it is never reached
a second time. A missing, malformed, unknown, or self-referencing code is
never an error; registration always succeeds regardless of what the
client-supplied header says.

**Trigger: first chest opened, paid or free.** Ported in spirit from
`pack_service._credit_referral_bonus`/`maybe_grant_referral_bonus_for_
locked_user`: football's own comment is explicit about why the reward
can't fire at registration — "crediting it immediately on registration
would let anyone farm referral rewards with disposable, never-played
accounts via this client-supplied header alone." The same anti-farm
reasoning applies to RPG; "first chest opened" (not "first hero created")
was chosen as the stronger engagement signal, matching football's own
choice of "first pack opened" over "registered" — and football's own
`claim_free_pack` independently checks the same gate, confirming "paid or
free, whichever comes first" is the intended shape there too, not
something RPG invented. Because RPG already unifies free and paid chest
opening into the single `chest_service.open_chest` function (Chest.price
already representing "free" as 0 — see below), the referral check needed
exactly **one** call site, where football needed three
(`open_pack`/`claim_free_pack`/`grant_bonus_pack_opening` each check it
independently). No referral-awareness was added to `battle_service`,
`expedition_service`, `quest_service`, `arena_service`, or `hero_service`.

**Reward: coins only (25), via `reward_service.grant_hero_reward` with
`xp=0`.** Matches football's own referral bonus, which is coins-only too
(it has no hero/XP concept at all). No new config table for the amount —
same reasoning as Arena's reward constants (Stage 9): no natural
per-template row for a referral bonus to live on, so it's a plain module
constant in `referral_service.py`.

**The referrer-has-no-hero edge case is deliberately unresolved, not
special-cased.** `grant_hero_reward` needs a real `hero_id` even for
`xp=0` (`grant_xp` locks the hero row regardless of amount). If the
referrer has never created a hero, `maybe_grant_referral_reward` simply
returns without granting anything and without setting `referral_reward_
granted` — the referred user's chest opening must never fail because of
the *referrer's* account state, and there is no retry/self-heal mechanism
for this case in V1. Verified live: two genuinely concurrent chest
openings by a freshly-referred user credited the referrer exactly once
(+25, not +50), confirming the gate holds under real Postgres concurrency
even though both chest openings themselves succeeded independently (paid
chests are supposed to be repeatable — only the referral reward is
one-shot).

**Locking order:** the referred user is already locked by `open_chest`
before `maybe_grant_referral_reward` runs; the referrer is locked *after*
that, not as a pre-sorted pair. This is the same narrow, accepted deadlock
shape football's own `maybe_grant_referral_bonus_for_locked_user`
documents (its caller already holds one lock before this function takes
the second) — and unlike football, no code path in RPG today locks a
(referrer, then some other specific user) pair in the reverse order, so
here the risk is currently vacuous, not just narrow. Worth re-checking if
a future feature ever introduces such a path.

### Free Chest: an ordinary `Chest` row, cooldown derived from `ChestOpening`

`Chest.price` already being a plain integer column means `price=0`
already correctly represents "free" — no new column, no new
`TransactionType` (still `chest_purchase`, just for a 0 amount;
`debit_coins(0)` is a harmless no-op transaction, same as any
`reward_service` caller granting `xp=0`). The free chest is a real seeded
`Chest` row (`slug="free-chest"`), opened through the **exact same**
`chest_service.open_chest` — same level gate, same loot roll, same
`ChestOpening` record, same referral trigger. No `FreeChestOpening` table.

**Cooldown is derived, one step past football's own `free_pack_service.py`
design.** Football stores `User.free_pack_available_at` directly — a real
column, because football has exactly one designated free-pack slot per
user (`GameConfig.free_pack_pack_slug`), so there's nowhere else for that
timestamp to live. RPG already records every chest opening's timestamp in
`ChestOpening`, so a second copy of "when did they last open the free one"
on `User` would just be a stale-able cache of information that's already
there. `free_chest_service._next_available_at()` computes it as
`MAX(ChestOpening.created_at WHERE user_id=X AND chest_id=<free-chest's
id>) + 24h`, purely at read/claim time — no `User.free_chest_available_at`
anywhere, confirmed by a test asserting the attribute doesn't exist on the
model.

**Why `claim()` takes its own lock before re-checking the cooldown, not
just before delegating to `open_chest`.** The first design considered was
a thin "check cooldown, then call `open_chest`" wrapper — this does NOT
work under concurrency: `open_chest` itself has no cooldown concept to
re-enforce (repeat purchases of a *paid* chest are the normal, intended
behavior, so nothing in it re-validates "haven't I done this recently").
Two concurrent claims would both pass a lock-free pre-check (neither has
opened it yet) and both succeed. The fix: `free_chest_service.claim()`
calls `wallet_service.lock_user_for_update` itself, *before* re-reading
the cooldown, then delegates to `open_chest`, which re-acquires the same
row's lock internally — a harmless no-op re-acquisition, since Postgres
row locks are reentrant within one transaction, not a second lock. This is
what actually serializes two concurrent claims: the second blocks until
the first's entire transaction (including `open_chest`'s own commit)
finishes, then re-reads the now-committed `ChestOpening` and correctly
sees the cooldown active. Verified live: two genuinely concurrent
`POST /chests/free/claim` calls — exactly one succeeded, the other got a
clean `ConflictError`, exactly one new `ChestOpening` row.

No idempotency-key mechanism was added for the free-chest claim — none
was needed once the lock-then-recheck shape above is correct; the cooldown
check itself, re-verified after the lock, *is* the safety mechanism the
brief asked for ("cooldown повторно проверяется после FOR UPDATE").

### Why no `GameConfig`

Both features needed exactly one or two tunable numbers (referral reward
amount, free chest cooldown hours) with no natural per-template row to
live on. Consistent with the Stage 8 audit's finding and Stage 9's own
precedent (`ARENA_WIN_REWARD_XP`/`_COINS`): a `GameConfig` singleton is
deferred until a genuinely cross-cutting number appears that doesn't fit
this pattern — two more single-purpose module constants don't meet that
bar.

### Scope explicitly not built in Stage 10

A `Referral`/`ReferralCode` table, a stored `referral_count` column, a
stored free-chest cooldown column anywhere, a `FreeChestOpening` table, a
new `TransactionType` for the free chest, `GameConfig`, Redis, a
background worker, Celery, an event bus, a `/referrals` list endpoint, and
any change to Battle/Expedition/Quest/Arena's internals. All explicit
exclusions in the brief, not oversights.

## Profile and Leaderboards (Stage 11)

Read-only aggregation over Battle, Arena, Expedition, Quest, ChestOpening
and User/UserHero — no counters, no leaderboard tables, no rating system.
Two new files pairs: `services/profile_service.py` + `routers/profile.py`,
`services/leaderboard_service.py` + `routers/leaderboards.py`. Zero new
tables, zero new columns. One index added (`arena_matches.winner_user_id`).

### Profile is pure derive-from-source, same principle as everywhere else

`GET /profile/me` and `GET /profile/{user_id}` never write anything —
no lock, no `db.add`, no `db.commit`. `profile_service.get_statistics()`
issues **one query with ten independent scalar subqueries and no FROM
clause**:

```python
select(
    select(func.count(Battle.id)).where(Battle.user_id == user_id).scalar_subquery(),
    select(func.count(Battle.id)).where(Battle.user_id == user_id, Battle.result == BattleResult.won).scalar_subquery(),
    ...  # 8 more, one per statistic
)
```

Each subquery aggregates its own table independently; there is no join
between Battle/ArenaMatch/UserExpedition/UserQuest/ChestOpening at any
point, so there is no possibility of the row-multiplication a single
multi-table `JOIN ... GROUP BY` would risk (e.g. joining Battle and
ChestOpening on `user_id` directly would multiply a user's battle count by
their chest count — a real bug class, deliberately never introduced).
`losses` is `played - wins` in Python (no draw state exists on Battle or
ArenaMatch, so this is exact, not an approximation). This is "several
independent aggregate queries" collapsed into one round-trip, not "one
giant query with many joins" — the brief's own distinction.

`ProfileOut.user` reuses the existing `UserMeOut` wholesale (same shape
`GET /auth/session` already returns, including `active_hero` via
`hero_service.hero_to_out`) rather than duplicating hero fields into a
parallel schema — a viewer already knows this shape from login.

**Arena "played" counts finished matches only** (`status = 'finished'`,
`player_a_user_id = X OR player_b_user_id = X`), not running ones — an
in-progress match has no result yet, so counting it as "played" would be
wrong the moment two profiles are compared mid-match. **Arena "wins"**
counts `winner_user_id = X`, the same column now indexed for the
leaderboard, so profile and leaderboard read wins the same way.

### Referral statistics reuse Stage 10's exact two columns

`referral_count` = `COUNT(users WHERE referred_by_id = X)` (everyone who
registered with X's code — "invited"). `successful_referrals` =
`COUNT(users WHERE referred_by_id = X AND referral_reward_granted = true)`
("converted" — opened their first chest, per Stage 10's trigger). Both
computed inline in the same scalar-subquery block as the other eight
statistics — no separate round-trip through `referral_service`'s existing
`referral_count()`/`total_referred_count()` helpers, because those return
an already-awaited `int` each, which would turn the profile's "one query"
design back into several. The two existing helpers stay as the public
API other callers (`auth.py`'s `UserMeOut.referral_count`) already use;
`profile_service` duplicates the equivalent SQL rather than composing
those functions, a deliberate, narrow exception to "don't duplicate
logic" in exchange for "don't reintroduce N+1."

### Public profile: an explicit allow-list, not a redacted private one

`PublicProfileOut`/`PublicStatisticsOut` are separate Pydantic models from
`ProfileOut`/`ProfileStatisticsOut` — not the private schema with fields
stripped at serialization time. `get_public_profile()` builds the public
response field-by-field from scratch, so there is no field on the private
model that could leak into the public one by a future edit forgetting to
exclude it; anything not explicitly assigned onto `PublicProfileOut`
simply cannot appear. Never-public: `telegram_id`, `balance`,
`referral_code`, `referral_count`/`successful_referrals`, any internal
foreign key beyond `user_id` itself (which the frontend already uses as
the public identifier for arena opponents and quest/battle history, so no
new "safe id" was invented). Verified live (Stage 11 report) and by
`test_public_profile_excludes_private_fields`, which asserts the raw JSON
keys, not just the typed model.

A nonexistent `user_id` is a genuine 404 (the user doesn't exist), unlike
every "no data yet" case elsewhere in Profile/Leaderboards, which returns
zeros/nulls, never 404 — a user with no hero, no battles, and no coins is
not a missing resource.

### Leaderboards: `RANK()` computed once, reused for both the page and `my_rank`

Each of the four types (`level`, `pve_wins`, `arena_wins`, `coins`) is one
`Select` that already carries `func.rank().over(order_by=...)` as a
column — built once per request, wrapped as a subquery, then read three
different ways from that same subquery: `COUNT(*)` for `total`, a
`LIMIT/OFFSET` slice ordered by `rank` for the page of `entries`, and a
`WHERE user_id = viewer` lookup for `my_rank`/`my_value`. There is exactly
one tie-break rule per type, defined in exactly one place (the `ORDER BY`
inside the window function) — `my_rank` can never disagree with where
that same user would appear in `entries`, because both come from the same
computed `rank` column, not two independently-written formulas.

Every ranking is a fully deterministic three-key sort, so no two distinct
users can tie for the same rank:

| Type | Order |
|---|---|
| `level` | `UserHero.level DESC, UserHero.xp DESC, User.id ASC` |
| `pve_wins` | `wins DESC, UserHero.level DESC NULLS LAST, User.id ASC` |
| `arena_wins` | `wins DESC, UserHero.level DESC NULLS LAST, User.id ASC` |
| `coins` | `User.balance DESC, User.id ASC` |

`pve_wins` and `arena_wins` build their win counts as a `GROUP BY`
subquery first (`Battle`/`ArenaMatch` grouped by the scoring user), *then*
join that already-aggregated subquery to `User`/`UserHero`/`HeroTemplate`
for display columns — never the reverse. Aggregating before joining is
what keeps a user's own hero/template row from being counted more than
once; joining `Battle` to `User` directly and then `GROUP BY user.id`
would still be correct here only by accident of there being one hero per
user — the subquery-first shape doesn't depend on that. A user with zero
wins never enters the `wins` subquery at all (an `INNER JOIN` against it),
so they simply don't appear in `entries`/`total` for that leaderboard —
confirmed live and by `test_pve_wins_leaderboard_my_value_zero_when_no_wins`,
where `my_rank` comes back `null` and `my_value` comes back `0` rather
than a fabricated last-place rank.

**`coins` is the user's current `balance`, explicitly not "total coins
ever earned."** Those are different metrics — a user who earned 10,000
coins and spent 9,900 of them is not more "successful" than one who
earned and kept 500, but a *total earned* leaderboard would rank the
first higher. The API field is named `coins` in the type literal and
`value`/`balance` in the response, never `total_coins_earned`, and no
`SUM(CoinTransaction)` query was written for this stage.

**No `arena_rating`/MMR/season/league anywhere.** `arena_wins` is a raw
`COUNT`, identical in kind to `pve_wins` — Stage 9 already declared "no
matchmaking, no rating for V1" and this stage doesn't quietly reintroduce
one through a leaderboard formula.

### The one index: `ix_arena_matches_winner_user_id`

Migration `0011_leaderboard_indexes.py`. Every other leaderboard/profile
query was checked against the existing schema first and found already
covered: `Battle.user_id` (existing index, used by both the pve_wins
`GROUP BY` and the profile subqueries), `UserExpedition.user_id`,
`ArenaMatch.player_a_user_id`/`player_b_user_id` (existing indexes, used
by the profile "arena played" filter), `User.referred_by_id` (Stage 10).
`ArenaMatch.winner_user_id` was the one genuine gap — the arena_wins
`GROUP BY` filters and groups on it directly, and neither existing
`ArenaMatch` index covers it. `Battle.result` and `UserHero.level`/`xp`
were evaluated and *not* indexed: at V1's data volume every `EXPLAIN` on
the real `rpg-postgres` container (see Stage 11 report) came back as a
`Seq Scan` that Postgres itself prefers over an index at this table size,
with no nested-loop blowup or cartesian product in any plan — adding
indexes Postgres wouldn't use yet is exactly the kind of premature
optimization this project's brief asks to avoid. Revisit if `EXPLAIN
ANALYZE` on real data volume ever shows otherwise; not a Stage 11 problem.

### Pagination

`limit` (1–100, default 20) and `offset` (≥0, default 0) as plain
`Query(...)` validators on the router — no shared pagination helper
existed anywhere in this codebase before Stage 11, and two parameters on
one endpoint didn't justify inventing one. `total` is a `COUNT(*)` over
the same ranked subquery the page comes from, so it always matches what
paging through `entries` would eventually enumerate.

### Scope explicitly not built in Stage 11

`leaderboards`/`leaderboard_entries` tables, any `user_statistics`/
`hero_statistics` table, stored `total_wins`/`total_battles`/
`total_xp_earned`/`total_coins_earned` columns anywhere, `arena_rating`/
MMR/seasons/leagues/trophies, leaderboard snapshots, Redis, Celery, a
background worker, an event bus, an analytics pipeline, achievements,
notifications, and a generic pagination helper module. All explicit
exclusions in the brief, not oversights; performance optimizations beyond
the one index above are deferred until a real `EXPLAIN ANALYZE` on
production-scale data shows a genuine problem.

## Admin CRUD for the remaining catalogs

`admin_chests.py` (Stage 5) was, until now, the only admin-write router that
existed — races, classes, hero templates, enemies, items, expeditions, and
quests were admin-*readable* only via their public, `is_active`-filtered
GET endpoints. This adds one admin router per resource
(`admin_races.py`, `admin_classes.py`, `admin_hero_templates.py`,
`admin_enemies.py`, `admin_items.py`, `admin_expeditions.py`,
`admin_quests.py`), each a structural copy of `admin_chests.py`'s own
shape: `GET` (unfiltered — includes inactive rows), `POST` create, `PUT`
update, `POST .../{id}/toggle-active`. No new tables, no migration — every
one of these models already had `is_active`/`sort_order` columns sitting
unused by any admin endpoint.

**Separate Out/Create/Update schemas (`schemas/admin.py`), not reused public
ones.** The existing `RaceOut`/`EnemyOut`/`ItemTemplateOut`/etc. schemas
deliberately omit `is_active`/`sort_order` — a player has no reason to see
either. Admin needs to see and edit both, so rather than widen the public
schemas (which would leak those fields to every player-facing response,
however harmlessly) or make `is_active` conditionally visible, admin gets
its own parallel `*AdminOut`/`*Create`/`*Update` types. Immutability
choices mirror existing precedent: `code`/`slug`-style identifiers
(`Race.code`, `CharacterClass.code`, `QuestDefinition.code`) are
create-only, matching `Chest.slug`; `ItemTemplate.slot/tier/rarity` are
create-only too, for the same reason `Chest.tier` already is — every
`UserItem`'s power is derived from those three at read time
(`item_progression.py`), so changing them post-creation would silently
reprice every item already granted from that template.

**Items: affix replacement bug found and fixed during testing.**
`ItemTemplate.affixes` has no `cascade="all, delete-orphan"` (unlike
`Chest.rarity_probabilities`, which does) — `item.affixes.clear()` tried to
`UPDATE item_affixes SET item_template_id = NULL`, which fails the
column's `NOT NULL` constraint. Fixed with an explicit `DELETE` targeting
`item_template_id`, plus `db.expire(item, ["affixes"])` before adding the
replacement rows — a raw bulk `DELETE` doesn't update the ORM session's
in-memory view of `item.affixes`, and touching that stale collection
afterward raises "Instance has been deleted." Scoped entirely to the new
`admin_items.py`; the model itself wasn't changed.

**Auth**: identical bearer-JWT pattern to `admin_chests.py` — no new
mechanism. Notably, **this is the first test coverage `get_current_admin`
has ever had** in this codebase; `admin_chests.py` shipped in Stage 5 with
zero tests exercising the admin path. `tests/conftest.py` gained one env
var (`RPG_ADMIN_TELEGRAM_IDS`) to make an admin-scoped test session
obtainable at all.

**Still not admin-editable, on purpose**: no hard delete anywhere (matches
`Chest`'s own toggle-active-only precedent — deactivation is the deletion
mechanism for a catalog row with historical references); no bulk
import/export; no image upload (same "no static-asset serving yet" reason
`admin_chests.py` already gives); no audit log of who changed what.

*(Both "no image upload" and "no static-asset serving" above are now out of
date — see the two sections immediately below, added in the same pass that
built admin user search/moderation.)*

## Admin user search, detail, and moderation

`admin_users.py` — the first admin router that isn't a catalog CRUD
resource. `GET /admin/users?search=&limit=&offset=` (search matches
username via `ILIKE` or an exact `telegram_id` when the search string is
all digits), `GET /admin/users/{id}` (adds full `ProfileStatisticsOut` by
calling `profile_service.get_statistics` directly — Stage 11's function,
not re-derived a second way), `GET /admin/users/stats` (live aggregate:
total/banned/admin counts, users with a hero, total balance in
circulation — one scalar-subquery `SELECT`, same shape Stage 11 already
established, no counters table).

**Moderation reuses existing primitives, adds none.** `is_banned` already
existed on `User` (checked in `get_current_user` since Stage 1) but nothing
had ever set it — `POST /admin/users/{id}/toggle-ban` is the first writer.
`POST /admin/users/{id}/grant-coins` reuses `wallet_service.lock_user_for_update`
+ `credit_coins` with `TransactionType.admin_grant` (existed since Stage 5,
also previously unused by any endpoint) — the exact same lock-then-credit
shape every other coin-granting code path in this app already uses, not a
new one. An admin can't ban another admin (`ConflictError`) — a narrow
guard against accidental lockout, not a permissions system.

**A real bug caught before shipping**: `wallet_service.lock_user_for_update`
raises `NoResultFound` (via `.scalar_one()`) for a missing id rather than
returning `None` — both moderation endpoints originally had a dead
`if user is None` check that would never run, meaning a bad `user_id`
would have surfaced as an unhandled 500 instead of a clean 404. Fixed by
checking existence with a lock-free `db.get()` before taking the row lock.

## Admin image upload

Local-disk storage, structurally the same shape as the football app's own
`image_service.py` (validate extension/content-type/size, sanitize the
filename, write under a per-resource directory, return the DB-stored
relative path) — not copied, trimmed to the four resource kinds that
needed it (`heroes`, `enemies`, `items`, `expeditions`) instead of
football's longer list, and unified into one `save_template_image(upload,
kind, display_name)` function instead of one function per entity type.

**This is not Stage 12's (design-only) AI artwork pipeline.** No status
machine, no versioning, no provider abstraction — it's the same
one-image-per-template model `image_path` has implied since Stage 1 on
every catalog model; this just finally puts a real file behind it.
`POST /admin/{resource}/{id}/image` (multipart) on each of the four admin
routers replaces whatever `image_path` already pointed at (old file
deleted best-effort after the new one is committed, never before — a
failed upload can't orphan a working image) and returns the updated row.
Static files are served back at `/static/...` (`app.mount` in `main.py`);
the directory is created lazily by the image service, not eagerly by the
app — nothing to create until the first upload.

**`ExpeditionTemplate` gained a real column** (migration `0012`,
`image_path`, nullable) — every sibling catalog model already had this
since its own migration; expeditions were the one holdout, because no
"location" concept existed for them before now. Added to the *public*
`ExpeditionTemplateOut` too (previously the only Out schema in this
backend without an `image_path` field, despite the model existing) —
purely additive, and while updating it, `expedition_service.template_to_out`
needed the same field added to its manual constructor call or every
existing expedition-listing request would have started failing Pydantic
validation on a newly-required field it never used to have to fill in.

**Scope not built, on purpose**: no image resizing/thumbnailing, no CDN,
no S3-compatible object storage (still local disk — same tradeoff football
already made and this explicitly isn't Stage 12's provider-agnostic
pipeline), no per-stage/versioned artwork, no bulk upload.
