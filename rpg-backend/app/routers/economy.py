from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.economy import WalletOut

router = APIRouter()


@router.get("", response_model=WalletOut)
async def get_wallet(user: User = Depends(get_current_user)):
    return WalletOut(coins=user.balance)
