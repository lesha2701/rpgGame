from typing import Literal

from pydantic import BaseModel

from app.schemas.battle import BattleLogEntryOut


class ArenaParticipantOut(BaseModel):
    user_id: int
    hero_id: int
    hero_name: str
    current_hp: int
    max_hp: int
    has_acted_this_round: bool


class ArenaMatchOut(BaseModel):
    id: int
    status: str
    current_round: int
    round_deadline_at: str
    player_a: ArenaParticipantOut
    player_b: ArenaParticipantOut
    log: list[BattleLogEntryOut]
    winner_user_id: int | None
    reward_xp: int
    reward_coins: int
    created_at: str
    finished_at: str | None


class StartArenaMatchRequest(BaseModel):
    opponent_user_id: int


class ArenaActionRequest(BaseModel):
    # The round this action is FOR, from the client's own last-seen state
    # (match-creation response or the previous action/GET response) — this
    # is what makes a retried request after the round already resolved
    # safely detectable as stale rather than being applied to whatever the
    # NEW current round happens to be. See arena_service.submit_action.
    round: int
    action_type: Literal["basic_attack", "skill"]
    skill_id: int | None = None
