from fastapi import APIRouter

from ..config import get_workspace_client
from ..governance.groups import list_workspace_groups

router = APIRouter()


@router.get("/groups")
def get_groups():
    client = get_workspace_client()
    groups = list_workspace_groups(client)
    return {"groups": groups}
