from fastapi import APIRouter

from .. import db

router = APIRouter()


@router.get("/trail")
async def get_trail(limit: int = 50):
    trails = await db.get_trails(limit)
    return {"trail": trails}
