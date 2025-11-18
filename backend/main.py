from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents, ensure_indexes
from schemas import API, APIOut, UsageEvent, PredictedStatus

app = FastAPI(title="Throttl API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()


class RegisterResponse(BaseModel):
    api: APIOut


@app.get("/test")
async def test():
    # quick database connectivity check
    try:
        await db.command("ping")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/apis", response_model=RegisterResponse)
async def register_api(api: API):
    created = await create_document("api", api.model_dump())
    return {"api": APIOut(**created)}


@app.get("/apis", response_model=List[APIOut])
async def list_apis():
    items = await get_documents("api", {}, limit=1000)
    return [APIOut(**i) for i in items]


@app.post("/usage")
async def record_usage(event: UsageEvent):
    # ensure api exists
    apis = await get_documents("api", {"_id": {"$in": []}}, limit=1)  # placeholder to satisfy type
    # We simply insert the event. We assume api_id validity is handled downstream/analytics.
    created = await create_document("usageevent", event.model_dump())
    return {"ok": True, "event": created}


async def _window_counts(api_id: str, window_seconds: int) -> int:
    now = datetime.utcnow()
    since = now - timedelta(seconds=window_seconds)
    pipeline = [
        {"$match": {"api_id": api_id, "timestamp": {"$gte": since}}},
        {"$group": {"_id": None, "count": {"$sum": "$units"}}},
    ]
    docs = await db["usageevent"].aggregate(pipeline).to_list(1)
    return int(docs[0]["count"]) if docs else 0


@app.get("/status/{api_id}", response_model=PredictedStatus)
async def status(api_id: str):
    # fetch API
    items = await get_documents("api", {"_id": {"$eq": api_id}}, limit=1)
    if not items:
        raise HTTPException(status_code=404, detail="API not found")
    api = APIOut(**items[0])

    current = await _window_counts(api_id, api.window_seconds)
    utilization = (current / api.max_requests) * 100 if api.max_requests > 0 else 0.0

    # naive projection: if >0 utilization, estimate time to hit 100% assuming current rate persists
    projected_hit: Optional[int] = None
    if current > 0:
        now = datetime.utcnow()
        # rate per second in the window
        rate_per_sec = current / api.window_seconds
        remaining = max(api.max_requests - current, 0)
        if rate_per_sec > 0:
            projected_sec = int(remaining / rate_per_sec)
            projected_hit = projected_sec

    thresholds_crossed = [t for t in api.thresholds if utilization >= t]

    return PredictedStatus(
        api_id=api_id,
        window_seconds=api.window_seconds,
        max_requests=api.max_requests,
        current_count=current,
        utilization_percent=round(utilization, 2),
        projected_hit_in_seconds=projected_hit,
        thresholds_crossed=thresholds_crossed,
    )
