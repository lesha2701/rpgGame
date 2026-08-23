# Frontend ↔ Backend API Map

Audit of `rpg-backend/` as it exists after Stage 11 (Stage 12 — artwork pipeline —
is design-only, nothing built yet: no `current_artwork_url`, no artwork tables,
no artwork endpoints). This file is the single source of truth for what each
screen in the approved Ember & Iron v3 direction can actually do against the
real backend today, versus what's mocked because the API doesn't exist yet.

Nothing here is invented. Every endpoint/field below was read directly from
`rpg-backend/app/routers/*.py` and `rpg-backend/app/schemas/*.py`.

## Auth

`POST /api/v1/auth/session` — Telegram `initData` (header `X-Telegram-Init-Data`)
or dev mode (`X-Dev-Mode: true`, only when backend `DEV_MODE=true`). Returns
`SessionResponse { user: UserMeOut, admin_token: string | null }`.
`GET /api/v1/auth/me` — same `UserMeOut` shape, no session side-effects.

`UserMeOut`: `id, telegram_id, username, first_name, last_name, active_hero
(UserHeroOut | null), referral_code, referral_count`.

Status: **fully usable now.** Implemented in `services/api/auth.ts`, driven by
`store/authStore.ts`.

## Home / Hero

`GET /heroes/me` → `UserHeroOut` (also embedded in `UserMeOut.active_hero`, so
Home doesn't need a second call — it reads `active_hero` from the session).
`POST /heroes` → creates a hero from a `hero_template_id` (only relevant for a
brand-new player with no hero yet).

`UserHeroOut`: `id, level, xp, xp_to_next_level, visual_stage, hero_template
(HeroTemplateOut), stats (HeroStatsOut)`. `HeroTemplateOut` carries
`image_path` (nullable string, **not** a real served file — no static-asset
serving exists on this backend) and nested `race`/`character_class`.

`GET /races`, `GET /classes`, `GET /hero-templates` — catalog, needed only for
hero creation (no hero yet).

Status: **fully usable now.** No `current_artwork_url` field exists anywhere
in `UserHeroOut`/`HeroTemplateOut` — Stage 12's artwork pipeline is design-only.
`ArtFrame` therefore always renders its **empty/upload** state for hero
portraits until that field ships; nothing here fakes an image URL.

## Hero Progression

No dedicated endpoint. `visual_stage` (already on `UserHeroOut`) is the only
real data point — computed server-side by
`progression.visual_stage_for_level(hero.level)`, 1..10. The 10-stage path
itself (labels, per-stage unlock levels 1/11/21…91) is **derived client-side**
from the same cadence (`LEVELS_PER_TIER = 10`, `MAX_LEVEL = 100`, both already
public via the level/XP numbers the API returns) — not invented, just the
inverse of the same formula the backend uses. No artwork per stage exists yet
(same Stage 12 gap as above) — every stage thumbnail uses `ArtFrame`'s empty
state; only the *current* stage is visually distinguished by rarity-style
framing, not by having a real image.

Status: **real progress number, mocked stage thumbnails** (no artwork field to
mock from — legitimately absent, not a placeholder standing in for real data).

## Profile

`GET /profile/me` → `ProfileOut { user: UserMeOut, balance, statistics }`.
`GET /profile/{user_id}` → `PublicProfileOut { user_id, username, hero:
PublicHeroOut | null, statistics: PublicStatisticsOut }`.

Status: **fully usable now.**

## Leaderboards

`GET /leaderboards/{level|pve_wins|arena_wins|coins}?limit&offset` →
`LeaderboardOut { type, entries: LeaderboardEntryOut[], total, limit, offset,
my_rank, my_value }`. `LeaderboardEntryOut { rank, user_id, username, hero:
{name, level} | null, value }`.

Status: **usable now**, staged for Phase 3 per the plan below (not wired this
pass — page exists, routed, shows a static mock).

## Battles (PvE)

`GET /enemies`, `GET /enemies/{id}` → `EnemyOut` (stats + `image_path`, same
no-real-file caveat as heroes).
`POST /battles { enemy_template_id, idempotency_key? }` → `BattleOut` —
**resolves synchronously in one call**, returns a fully-computed `log:
BattleLogEntryOut[]` (turn/attacker/target/action_type/damage/critical/
target_hp_after) to replay client-side. There is no "submit one action, get
one response" flow for PvE — the whole fight already happened server-side.
`GET /battles`, `GET /battles/{id}` — history.

Status: **usable, wired.** Now lives at `/battle/pve` under the restructured
Battle hub (`/battle`) rather than being the direct target of the "Бой" tab —
see "Battle hub + mini-games" below.

## Arena (PvP)

`POST /arena/matches { opponent_user_id }`, `GET /arena/matches`,
`GET /arena/matches/{id}`, `POST /arena/matches/{id}/action { round,
action_type, skill_id? }`. Real round-by-round state (`current_round`,
`round_deadline_at`, both participants' HP, `log[]`).

**Gap, confirmed again from Stage 11 analysis:** there is no endpoint to list
or search opponents — `opponent_user_id` must already be known. The Arena
screen's opponent picker has nothing to call; shown as an explicit
"coming soon" state, never a fake user list.

Status: **usable, wired.** Reachable from the restructured Battle hub
(`/battle` → "Арена" tile → `/arena`), no longer buried in "Ещё".

## Battle hub + mini-games (later pass)

**Restructure**: "Бой" used to jump straight into the PvE enemy-picker.
Now `/battle` is a hub (`BattleHubPage`) listing every combat-adjacent
game mode — PvE (`/battle/pve`), Arena (`/arena`), and (new) two
mini-games — instead of Arena being one tap away from "Ещё" and PvE living
directly on the bottom-nav tab. The mini-games list is intentionally
open-ended (`MinigameType` on the backend has the same "extend later"
framing as `TransactionType`) — adding a third mini-game later means one
more tile here, not a restructure.

**Memory Sequence and Find the Pair — brand new backend, not adapted from
an existing endpoint.** Neither game existed in any form before this pass.
Both share one shape: `POST /minigames/{game}/start` generates a
server-side secret (a random symbol sequence / a shuffled pair layout),
persists it on a `MinigameAttempt` row (`payload` JSON — same "one blob for
the one piece of state that doesn't flatten into columns" precedent as
`ArenaMatch.state`/`Battle.log`) so scoring at `submit`/`complete` time
checks the *real* answer instead of trusting whatever the client echoes
back, then returns the secret to the client anyway (necessary — the player
has to see it to play) as `MemoryStartOut { attempt_id, sequence, symbols }`
/ `PairsStartOut { attempt_id, layout, symbols }`.
`POST /minigames/memory/{attempt_id}/submit { answer }` and
`POST /minigames/pairs/{attempt_id}/complete { moves }` →
`MinigameResultOut { success, reward_xp, reward_coins,
daily_rewarded_remaining, hero_progress }`. Reward grants go through
`reward_service.grant_hero_reward` — the same "lock user, grant_xp,
credit_coins" composition every other reward path in this app already
uses — under a new `TransactionType.minigame_reward`.

Pairs' reward scales by move-count efficiency (`PAIRS_COUNT`=6 moves is a
"perfect" clear → full reward; up to 2x → 60%; beyond that → 25%), with the
server clamping any client-reported `moves` below the mathematically
possible minimum rather than trusting it outright — not fully cheat-proof
(a client can still lie about its own move count), but consistent with
the low trust level a casual reward-capped mini-game needs, not a
competitive economy-critical system.

**New per-game hourly/daily attempt limits** — RPG had no prior mechanism
of this shape at all (every other RPG system gates differently: chests are
coin-gated, expeditions are one-active-at-a-time, quests are one-time).
`services/minigame_limits_service.py` is a fresh, generic implementation
(parametrized by a `MinigameLimitFields` dataclass so a third game reuses
it without new code) of a rolling-1h attempt cap (`HOURLY_ATTEMPT_LIMIT` =
10, blocks `start` with a 409 once spent) and a rolling-24h *rewarded*-
attempt cap (`DAILY_REWARDED_LIMIT` = 5 — once spent, `submit`/`complete`
still resolves normally, it just stops paying xp/coins). Two new columns-
pairs per game on `User` (`<game>_hourly_attempts`/`_hour_started_at`,
`<game>_rewarded_attempts_today`/`_attempts_reset_at`), migration `0015`.

**Reward tuning lives as plain module constants** (`MEMORY_REWARD_XP` =
15, `MEMORY_REWARD_COINS` = 10, `PAIRS_REWARD_XP` = 20, `PAIRS_REWARD_COINS`
= 15 in `minigame_service.py`), not a new admin-editable config table —
same precedent Arena's own `ARENA_WIN_REWARD_XP`/`COINS` already set for a
non-template game mode (Enemy/Expedition/Quest rewards live on their own
admin-editable template rows; a mini-game has no template row to put them
on). Not wired into the admin panel this pass.

Status: **usable, wired, fully tested** (13 new backend tests: correct/
wrong answers, double-submit rejection, cross-user attempt-ownership
rejection, hourly limit, daily rewarded cap, pairs reward tiers, moves
clamping, no-hero 404s). Verified live end-to-end in the browser for both
games, including a real reward grant reflected in balance/xp.

**Four more mini-games (follow-up pass): Training Dummy, Alchemy, Tavern
Dice, Three Cups** — `MinigameType` extended (migration `0017`, same
`ALTER TYPE ADD VALUE` shape as `0015`), each with its own 4-column
limit-field set on `User` (24 mini-game columns on `User` total now).
Reward-gating logic shared across all six games via a new
`_apply_daily_cap` helper in `minigame_service.py` (was duplicated 2x
before this pass, would've been 6x).

- **Training Dummy** (`dummy`) and **Alchemy** (`alchemy`) follow the exact
  same start/resolve shape as Memory/Pairs — `POST /minigames/dummy/start`
  returns a full `directions: string[]` prompt list (8 rounds,
  left/right/up/down) the client reveals one at a time with its own
  timer, reporting `hits` back to `.../complete`, reward-tiered by hit
  rate. Alchemy generates a `recipe: number[]` (a permutation of 6
  ingredient indices) revealed briefly then hidden, reproduced via tap-
  to-add-to-cauldron and submitted to `.../submit` for an exact-match
  check — mechanically identical to Memory Sequence, themed differently.
- **Tavern Dice** (`dice`) and **Three Cups** (`cups`) are genuinely
  multi-step — the *only* mini-games so far where a `MinigameAttempt` row
  stays `pending` across more than one follow-up call. Dice:
  `POST .../start` → `POST .../{id}/roll` (repeatable — 1/6 bust chance
  per roll, otherwise the roll value 2-6 adds to a pot; a
  `DICE_MAX_ROLLS`=10 soft cap auto-finishes) → `POST .../{id}/bank`
  (cash out the pot early). All three share one response shape,
  `DiceRoundOut`, so the frontend doesn't need three different result
  types. Cups: `POST .../start` picks a secret correct cup (0-2) for
  round 1 → `POST .../{id}/guess {cup}` — correct advances to a new
  secret cup for the next round (up to `CUPS_MAX_ROUNDS`=5, reward scales
  with rounds cleared), wrong ends the attempt immediately with no
  reward. Shared response shape `CupsRoundOut`.
- Frontend: `TrainingDummyPage`/`AlchemyPage`/`TavernDicePage`/
  `ThreeCupsPage`, all under `/battle/{game}`. `BattleHubPage`'s
  mini-games section switched from a full-width row list to a 2-column
  icon-card grid once it grew to six entries.

Status: **usable, wired, fully tested** (20 new backend tests, including
`unittest.mock.patch` on `random.randint` for deterministic dice-bust/
cups-guess assertions). Verified live in the browser for all four:
Training Dummy's round timer and hit tracking, Alchemy's real recipe
round-tripped from `start` and submitted correctly, Dice's roll → pot →
bank flow with the exact reward formula confirmed, Cups' correct guess
advancing from round 1 to round 2.

## Chests

`GET /chests`, `GET /chests/{id}` → `ChestOut` (price, rarity
probabilities, `image_path`). `POST /chests/{id}/open { idempotency_key? }` →
`ChestOpenResult { opening_id, chest, reward: ChestRewardOut, balance }`.
`GET /chests/free`, `POST /chests/free/claim`, `GET /chests/openings`.

Status: usable now.

**`Chest.tier` removed (later pass) — loot is now capped by the opening
hero's own tier, not the chest's.** A chest used to belong to a fixed
equipment Tier, which gated both which item tiers it could drop
(`item_template.tier == chest.tier`) and which hero level could even open
it. Both are gone: `chest_service.pick_random_item_template` now takes
`max_tier` (= `equipment_tier_for_level(hero.level)`) and rolls uniformly
across every item tier **1..max_tier**, and `open_chest` no longer has a
hero-level gate at all — any hero can attempt to open any chest they can
afford, they just never roll above their own tier's items regardless of
which chest they bought. Chests differentiate purely by
price/rarity_probabilities/guaranteed_min_rarity now (a "cheap" chest and
an "expensive" chest opened by the same tier-5 hero can both drop a tier-5
item — the expensive one is just far more likely to roll a good rarity).
`ChestOut`/`ChestSummaryOut` dropped `tier`, `required_hero_level`,
`is_available_to_user` accordingly — nothing to gate on anymore. Migration
`0014` narrowly renamed + rebalanced only the chests `app/seed.py` itself
created (`slug LIKE 'tier-%-chest'` and the free chest) to quality-named
odds tiers (Простой → Легендарный сундук); any chest an admin created by
hand (e.g. a real test row already in the live DB) was left completely
untouched — only its `tier` column disappeared, name/price/probabilities
unchanged. Verified live: a level-20 (tier 2) hero opening several
different-priced chests never once received above a tier-2 item.

**Chest-opening reveal animation (later pass, frontend-only).**
`ChestOpeningPage` used to render the reward instantly on mutation
success — no suspense at all. Now there's a staged "opening" beat (the
chest artwork jitters via a finite `animate-chest-shake` — translate + a
couple degrees of tilt, never a spin) held for a *minimum* 1.1s
(`MIN_SUSPENSE_MS`) even if the response comes back faster, then the
reward card pops in (`animate-card-pop-in`, a one-shot scale/opacity
transition). Also fixed a real pre-existing bug while touching this:
`RewardReveal` used to hardcode a legendary-gold border/glow on *every*
reveal regardless of the actual rolled rarity — now the border color and
the ambient glow/rays (only shown for rare+, silent for common) are tinted
by `reward.rarity`. Both the shake and the glow/rays stay within the
locked Ember & Iron v3 constraint — "breathing radial glow + static
twinkling rays, never rotating/conic effects" — verified by construction
(no `rotate()` keyframe loops anywhere in either animation).

**Two real bugs found and fixed in a follow-up pass**: (1) `ChestRewardOut`
never carried `image_path` even though `item_template_to_out` computed it
— `_build_open_result` built the reward manually field-by-field and simply
dropped it, so the reveal card always showed a generic "✦" glyph instead
of the real item photo; added the field to the schema and the constructor
call, and `RewardReveal` now renders a real `ItemArtwork`. (2) The shake/
pop-in animations from the first pass genuinely never fired in the
browser the user was testing in — the Tailwind config edit that added
`chest-shake`/`card-pop-in` happened while the dev server was already
running, and it never picked up the new keyframes until restarted. Fixed
by restarting the dev server; also bumped `MIN_SUSPENSE_MS` 1.1s→1.5s,
lengthened `card-pop-in` 0.55s→0.85s, and added a brief opacity-only
`reveal-flash` burst timed with the card's entrance, all to make the
reveal harder to miss now that it's confirmed actually rendering.

## Inventory / Equipment

`GET /heroes/me/inventory`, `GET /heroes/me/inventory/{id}` →
`UserItemOut { id, item_template: ItemTemplateOut, is_equipped,
equipped_hero_id }`. `GET /heroes/me/equipment` → `EquippedItemsOut` (7 named
slots). `POST /heroes/me/equipment/{user_item_id}/equip|unequip`.
`GET /item-templates` — catalog.

Status: usable now.

**Inventory stacking + dropdown filters (later pass, frontend-only, no
backend change).** The inventory list is still one row per `UserItemOut`
instance server-side — `InventoryPage.tsx` groups client-side by
`(item_template.id, is_equipped)` into stacks (`groupStacks`) and renders
one `ItemCard` per stack with a `count` prop → a `×N` badge, instead of N
near-duplicate cards for N identical unequipped copies. Equip/unequip acts
on the stack's representative instance's id (any instance works, they're
identical by template) — equipped copies are never stacked with unequipped
ones of the same template since equip state is part of the grouping key
(and at most one instance of a template can be equipped at a time anyway).
The slot/rarity filter row was originally a horizontally-scrolling chip
list — replaced with two native `<select>` dropdowns per explicit request
("неудобно что листать надо в сторону").

**Item detail sheet (follow-up pass, frontend-only).** Tapping any
inventory card (not the equip/unequip button, which stops propagation)
opens `ItemDetailSheet` — a bottom sheet with full artwork, name/rarity/
tier/slot, description, every non-zero stat, affixes, and the same equip/
unequip action. Everything it needs was already on `UserItemOut.
item_template` from the existing inventory fetch — no new endpoint.

**Item names simplified — tier/rarity suffix dropped from the name
entirely (follow-up pass, backend + data migration).** Every seeded item
used to be named like "Меч 1 тира (легендарный)" — redundant with what
the card already shows via its own rarity color/label and "T{n}" badge.
`seed.py`'s `_item_name` is now a pure function of `(slot, tier)` — 70
hand-written escalating names (`ITEM_NAMES_RU`), tiers 1-3 varying
material/craft per slot, tiers 4-10 sharing one prestige-word ladder
(страж → ветеран → рыцарский → чемпион → герой → легенда → владыка) so a
higher tier always reads as grander regardless of which rarity roll it
happens to be. This made `name` no longer unique per `(slot, tier)` — all
4 rarities of a given tier now share one name — so `_get_or_create_item_
template`'s idempotent seed lookup switched from keying on `name` to
keying on the real `(slot, tier, rarity)` columns. Migration `0016`
renamed the 280 already-seeded rows whose name still exactly
matched what the *old* generator would have produced for that row's own
(slot, tier, rarity) — same narrow "don't touch admin-customized rows"
discipline as the chest-rename migration.

## Quests

`GET /quests` → `QuestOut[]` (progress computed live, no separate progress
table). `POST /quests/{user_quest_id}/claim` → `QuestClaimOut` incl.
`hero_progress: HeroProgressOut`.

Status: usable now, staged for Phase 4.

## Expeditions

`GET /expeditions`, `GET /expeditions/{id}`, `GET /expeditions/history`,
`POST /expeditions/{id}/start`, `POST /expeditions/{user_expedition_id}/claim`.
`UserExpeditionOut.status` is `"running" | "completed" | "claimed"`; no
location/map artwork field exists on `ExpeditionTemplateOut` — the "journey"
visual framing from the design will use a generic/thematic scene, never a
per-expedition image.

Status: usable now, staged for Phase 4.

## Skills

`GET /heroes/me/skills`, `GET /heroes/me/skills/available`,
`POST /heroes/me/skills/{id}/upgrade`.

Status: usable now, not on the Phase 1–4 screen list yet (surfaced inside
Hero once Hero itself has real skill data wired — Phase 2/3, alongside
Equipment).

## Economy

`GET /economy` → `WalletOut { coins }`. Balance is also already present on
`ProfileOut.balance` — Home/Hero read it from the session/profile response,
not a separate call.

## Referral

No dedicated endpoints beyond what's already on `UserMeOut`
(`referral_code`, `referral_count`) and `ProfileOut.statistics.referrals`
(`referral_count`, `successful_referrals`). Surfaced inside Profile, not a
separate screen.

## Admin

`POST /auth/session` already returns `admin_token` (non-null only when
`RPG_ADMIN_TELEGRAM_IDS` includes the caller) alongside the regular user —
`UserMeOut` itself carries no `is_admin` field, so a non-null `admin_token`
in the session response is the only "is this an admin" signal the frontend
has. Admin requests authenticate via `Authorization: Bearer <admin_token>`
instead of the regular Telegram/dev-mode headers (`services/api/client.ts`
attaches it automatically for any request whose path starts with `/admin`),
mirroring the football frontend's identical pattern exactly.

**Every catalog resource now has a real admin-write router**, not just
chests. `admin_chests.py` (Stage 5) was the only one that existed when this
file was first written; races, classes, hero templates, enemies, items,
expeditions, and quests each gained their own `admin_*.py` router
(`GET` list-unfiltered / `POST` create / `PUT` update /
`POST {id}/toggle-active`), all added specifically for this pass — see
`rpg-backend/ARCHITECTURE.md`'s "Admin CRUD for the remaining catalogs"
section for the backend-side detail (including a real bug found and fixed
along the way: `ItemTemplate.affixes` replacement failing a NOT NULL
constraint because that relationship has no delete-orphan cascade).

Frontend-side, this is `admin/resources.ts` — one config-driven CRUD system
(`AdminResourceListPage`/`AdminResourceFormPage`) instead of seven
near-duplicate page pairs, since all seven routers share the exact same
shape. Chests keep their own dedicated pages (`AdminChestsPage`/
`AdminChestFormPage`) rather than joining the generic system — their shape
(price, rarity-probability breakdown, slug) doesn't fit the same field-list
model cleanly, and the existing implementation already worked.

**A real frontend bug was found and fixed during live verification**: the
generic form's `buildInitialState` looked up an editing item's existing
affixes under the wrong key (`affix_stat_types`, the *write* field name)
against a row that only has `affixes` (the *read* field name) — so editing
any item silently started from an empty affix list instead of the real one,
and saving would have wiped it. Confirmed by reproducing it live (edited a
real item, the multiselect showed nothing pre-selected, saving collapsed
its two real affixes down to whichever one got clicked) before fixing it
with an explicit `sourceKey` on the field config, then re-verified live
that the edit form now pre-fills correctly and a no-op save round-trips
the same two affixes unchanged.

**User statistics, search, and moderation** (added this pass): `GET
/admin/users` (search by username `ILIKE` or exact `telegram_id` if the
query is all-digits, paginated), `GET /admin/users/stats` (aggregate
counts/balance in one no-FROM scalar-subquery `SELECT`), `GET
/admin/users/{id}` (detail + `profile_service.get_statistics`), `POST
/admin/users/{id}/grant-coins` and `POST /admin/users/{id}/deduct-coins`
(added in a follow-up pass, mirrors grant exactly but calls
`wallet_service.debit_coins` — a real `InsufficientBalanceError`/400 if the
deduction would take the user negative, same guard every other coin sink
in this app already has; needed a new `admin_deduct` value on the
Postgres-native `transaction_type` enum, migration `0013`), `POST
/admin/users/{id}/toggle-ban` (blocks banning an admin account with a
`ConflictError`). Coin mutations route through the same
`wallet_service.lock_user_for_update`/`credit_coins`/`debit_coins` pattern
every other coin mutation in this app uses. Frontend: `AdminUsersPage`
(stat chips + search + table) and `AdminUserDetailPage` (stats grid +
shared amount/description inputs with a grant button and a deduct button
side by side + ban button). Verified live: granted coins to a real user
(balance incremented and persisted), deducted coins from the same user
(balance decremented and persisted), toggled ban/unban (login blocked via
`/auth/session` returning 403, then restored).

**Image upload** (added this pass): `POST /admin/{resource}/{id}/image`
(multipart, one per resource — hero-templates, enemies, items,
expeditions, and (added in a follow-up pass) chests) saves to
`rpg-backend/static/{kind}/` via `image_service.save_template_image` and
sets `image_path`; `/static` is mounted on the backend and proxied by Vite
dev (`vite.config.ts`). Frontend `staticUrl()` resolves `image_path` →
`/static/{path}` and every artwork wrapper
(`CharacterArtwork`/`EnemyArtwork`/`ItemArtwork`/`ChestArtwork`/
`ExpeditionArtwork`) now routes through it. Four resources use
`ImageUploadField` via the generic resource form's `imageUploadKind`;
chests keep their own dedicated form (`AdminChestFormPage`, since chests
never joined the generic resource system — see Admin section above) and
embed the same `ImageUploadField` directly with `basePath="/admin/chests"`.
Races/classes/quests have no image field and were deliberately left off
this list. Verified live: uploaded a real PNG to a real enemy via curl and
via the browser, confirmed it renders back through `/static/...` with the
correct content-type, and that the public `/enemies` list reflects it;
chest upload verified via a passing backend test
(`test_upload_chest_image`) plus confirming the upload field renders
correctly on a real chest's edit form (no in-browser file-picker
automation available in this environment to drive the upload itself).

**Expedition images were uploaded but never rendered in-game — found and
fixed this pass.** Root cause: `ExpeditionsPage.tsx` never read
`image_path` at all — both cards rendered a flat CSS gradient div, and no
`ExpeditionArtwork` wrapper existed (only `CharacterArtwork`/`EnemyArtwork`/
`ItemArtwork`/`ChestArtwork` did). Separately, the frontend's
`ExpeditionTemplateOut` type was missing the `image_path` field the
backend schema already had (added in an earlier pass for the upload
endpoint, but the frontend type was never updated to match) — so even
reading it would have been a type error. Fixed: added `image_path` to the
type, created `ExpeditionArtwork.tsx`, and wired it into both
`ExpeditionTemplateCard` (has a real `image_path` from the templates list)
and `ActiveExpeditionCard` (looks up the matching template from the
already-fetched templates list by id, since `ExpeditionSummaryOut` itself
carries no image field). Also sized up from the old `h-16` gradient to
`ArtFrame`'s existing `"battle"` size (`h-32`, double the height) per
explicit request — reused an existing size token rather than inventing a
new one. Verified live: real uploaded location art now renders on the
Expeditions screen for both the browse list and the in-progress card.

**Still not admin-editable, on purpose** (stated in the admin dashboard UI
itself, not just here): no hard delete anywhere — deactivation is the
deletion mechanism, matching `Chest`'s own precedent, for every one of
these eight resource types; no admin action audit log; no image
resize/CDN — uploads are served as-is from local disk. None of this is
faked — there is simply no backend endpoint for any of it yet.

## Artwork / `current_artwork_url`

**`current_artwork_url` itself still does not exist** — Stage 12
(`HeroArtworkStage`/`EnemyArtworkStage`, per-level-stage artwork) remains
design-only. What changed this pass: `image_path` on hero
templates/enemies/items/expeditions can now point at a **real served
file** via the admin image-upload endpoints (see Admin section above), so
`ArtFrame` and its wrappers do render a real image once one has been
uploaded for that template. Every artwork-bearing component still has to
treat "no artwork" as the **default, common case** for any template nobody
has uploaded an image for yet — reflected in the component API
(`components/artwork/ArtFrame.tsx`): `src` is always optional, and only
non-empty once `staticUrl(image_path)` resolves to something.

---

## Screen-by-screen status (Phase 4 build)

| # | Screen | Endpoint(s) | Real data now | Missing | Wired this pass |
|---|---|---|---|---|---|
| 1–2 | Hero (merged Home+Hero) | `GET /heroes/me` | hero, level, XP, stats, balance | equipment summary (Phase 2) | ✅ |
| 3 | Hero Progression | derived from `visual_stage` | current stage number | per-stage artwork | ⚠️ partial (real number, mock path) |
| 4 | Collection | `GET /hero-templates` + session | catalog + real "which template is selected" | multi-hero ownership (reinterpreted, see below) | ✅ (reinterpreted) |
| 5 | Character Detail | `GET /hero-templates` + session | real (owned: live stats; locked: class base stats) | — | ✅ (reinterpreted) |
| 6 | Bestiary | `GET /enemies` | full enemy list | artwork URL | ✅ |
| 7 | Enemy Detail | `GET /enemies/{id}` | full enemy | artwork URL | ✅ |
| 8 | Battle hub | static (routing only) | mode list | — | ✅ |
| 8a | Battle (PvE) | `POST /battles`, `GET /enemies` | real | — | ✅ |
| 8b | Memory Sequence | `POST /minigames/memory/start`/`.../submit` | real, interactive | — | ✅ |
| 8c | Find the Pair | `POST /minigames/pairs/start`/`.../complete` | real, interactive | — | ✅ |
| 9 | Arena | `POST/GET /arena/matches`, `POST .../action` | real | opponent search (manual ID input as workaround) | ✅ (with caveat) |
| 10 | Leaderboards | `GET /leaderboards/{type}` | real | — | ✅ |
| 11 | Chests | `GET /chests`, `GET /chests/free` | real | — | ✅ |
| 12 | Chest Opening | `POST /chests/{id}/open`, `POST /chests/free/claim` | real | — | ✅ |
| 13 | Inventory | `GET /heroes/me/inventory`, equip/unequip | real, interactive, slot/rarity filters | — | ✅ |
| 14 | Equipment | `GET /heroes/me/equipment`, equip/unequip | real, interactive | artwork URL | ✅ |
| 15 | Quests | `GET /quests`, `POST .../claim` | real, interactive | — | ✅ |
| 16 | Expeditions | `GET /expeditions`, `.../history`, start/claim | real, interactive | location artwork | ✅ |
| 17 | Profile | `GET /profile/me`, `GET /profile/{id}` | real | avatar artwork | ✅ |
| 18 | Settings / More | `GET /auth/me` (account info) | account, referral stats | notification prefs (no backend field) | ✅ |

**Collection / Character Detail — reinterpreted, not fixed by inventing a
backend feature.** `UserHero` is singular per user (`User.active_hero_id`) —
there is no multi-hero ownership, no "discovered/undiscovered" roster.
Rather than leave these stubbed, Phase 2 reads them as **"the game's hero
catalog, with your one active hero marked unlocked"**: `GET /hero-templates`
(real catalog) + the session's `active_hero.hero_template.id` (real) decide
which card is "owned" vs locked. A locked template's detail view shows its
`CharacterClassOut` base stats (level-1 numbers, real data) instead of
nothing. This is explicitly **not** the "gallery of owned heroes" the design
implies — it's the closest honest thing buildable from what exists. Flagged
again here for your confirmation; happy to revert to a plain stub if this
reinterpretation isn't wanted.

**Chest Opening — free chest routing.** The generic `POST /chests/{id}/open`
has no cooldown concept at all (only `free_chest_service.claim()`, reached
via `POST /chests/free/claim`, enforces it) — calling the generic endpoint
on the free chest's id would silently bypass the 24h limit. `ChestOpeningPage`
detects the free chest via `chest.slug === "free-chest"` and routes to the
dedicated claim endpoint; every other chest uses the generic open endpoint.
Verified live: claiming set a real cooldown, and a second attempt correctly
disabled the "Open" button with the real `next_available_at` timestamp.

**Battle — no per-turn action buttons.** `POST /battles` resolves the whole
fight synchronously and returns the finished `log[]` — there is no per-round
server call for PvE (unlike Arena). The approved design showed a 3-button
action row, but those would have to be fake (nothing to submit them to), so
Battle replays the real log at a fixed pace with HP bars and a log line
instead, plus a "Пропустить" skip control. This is a deliberate adaptation,
not a silent drop — flagged for confirmation like the others.

**Arena — opponent picker is a manual ID field.** Per the gap noted below,
there's no way to discover a real opponent, so `ArenaPage` has an explicit,
labeled workaround: type a known `user_id` and challenge them directly. Match
viewing/action submission (`ArenaMatchPage`) is fully real — verified live
against an actual in-progress match (id 3, round 4) created in an earlier
stage: submitting "Обычная атака" flipped `has_acted_this_round` to `true`
on the real backend, confirmed via direct API check.

**Nav restructuring (this pass):** Home and Hero were the same content
rendered twice at two routes — merged into one `HeroPage` (`HomePage.tsx`
deleted, `/` now redirects to `/hero`). The bottom nav's old "Дом" slot
(`/`) now points at Chests instead (`/chests`); "Вещи" was renamed
"Инвентарь" (same `/inventory` route, now with slot/rarity filter chips).
"Ещё" (`MorePage`) changed from a flat list of chevron rows to a 3-column
grid of icon cards, one per section (Сундуки dropped from this grid since
it now lives directly in the bottom nav).

**All 18 screens are now wired** (real, reinterpreted, or with an explicit
documented workaround — none left as silent stubs). Expeditions polls
`GET /expeditions/history` every 5s while any instance is `running`, mirroring
Arena's "no push, client polls" pattern — a running expedition becomes
`completed` purely by time passing (see ARCHITECTURE.md's Stage 7 section),
so nothing but a re-check ever notices. Verified live end-to-end: claimed a
real pre-existing completed-but-unclaimed expedition, started a fresh one,
watched its countdown tick down from a real `completed_at`.

## Backend gaps found (no backend changes made)

1. **No opponent list/search for Arena** — `POST /arena/matches` needs an
   `opponent_user_id` the client has no way to discover.
2. **No multi-hero ownership** — "Collection" as designed (a gallery of
   multiple owned heroes, locked/unlocked) has nothing to read from; today's
   model is one active hero per user.
3. **No per-level-stage artwork pipeline** — confirmed already in the Stage
   12 design report; `current_artwork_url` doesn't exist. (Static, single-image
   uploads per template now exist as of this pass — see Admin/Artwork
   sections above — but that's a flat "one image per template" model, not
   Stage 12's per-progression-stage artwork.)
4. **No per-expedition location artwork field.**

None of these were touched — flagging only, per your instruction not to
change the backend without separate confirmation.
