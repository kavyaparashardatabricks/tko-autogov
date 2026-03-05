from fastapi import APIRouter

from ..config import get_workspace_client
from ..governance.scan import list_catalogs

router = APIRouter()


@router.get("/catalogs")
def get_catalogs():
    client = get_workspace_client()
    cats = list_catalogs(client)
    return {"catalogs": cats}
