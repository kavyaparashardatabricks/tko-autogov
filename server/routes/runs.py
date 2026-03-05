import logging
import traceback

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..governance.pipeline import run_pipeline
from .. import db

logger = logging.getLogger(__name__)

router = APIRouter()

_active_runs: dict[str, dict] = {}


class RunRequest(BaseModel):
    catalog: str | None = None
    mode: str = "suggest"
    group_names: list[str] | None = None


@router.post("/run")
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Kick off a governance scan pipeline run."""
    try:
        result = await run_pipeline(
            catalog=req.catalog,
            mode=req.mode,
            group_names=req.group_names,
        )
        return result
    except Exception as e:
        logger.exception("Pipeline run failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )


@router.get("/runs")
async def list_runs(limit: int = 50):
    trails = await db.get_trails(limit)
    return {"runs": trails}


@router.get("/runs/{run_id}/classifications")
async def get_run_classifications(run_id: str):
    rows = await db.get_classifications(run_id)
    return {"run_id": run_id, "classifications": rows}
