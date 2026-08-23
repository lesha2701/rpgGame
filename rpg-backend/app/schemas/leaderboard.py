from pydantic import BaseModel


class LeaderboardHeroOut(BaseModel):
    name: str
    level: int


class LeaderboardEntryOut(BaseModel):
    rank: int
    user_id: int
    username: str | None
    hero: LeaderboardHeroOut | None
    value: int


class LeaderboardOut(BaseModel):
    type: str
    entries: list[LeaderboardEntryOut]
    total: int
    limit: int
    offset: int
    my_rank: int | None
    my_value: int
