from pydantic import BaseModel


class WalletOut(BaseModel):
    coins: int
