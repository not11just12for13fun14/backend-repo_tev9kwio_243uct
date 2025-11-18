import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "app")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(DATABASE_URL)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = _get_client()[DATABASE_NAME]
    return _db


# Exported database handle
db: AsyncIOMotorDatabase = get_db()


async def ensure_indexes() -> None:
    # Helpful indexes for queries
    await db["usageevent"].create_index([("api_id", ASCENDING), ("timestamp", ASCENDING)])
    await db["api"].create_index([("name", ASCENDING)], unique=False)


async def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    payload = {**data, "created_at": now, "updated_at": now}
    result = await db[collection_name].insert_one(payload)
    payload["_id"] = str(result.inserted_id)
    return payload


async def get_documents(
    collection_name: str,
    filter_dict: Optional[Dict[str, Any]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    cursor = db[collection_name].find(filter_dict or {}).limit(limit)
    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])  # stringify ObjectId
        items.append(doc)
    return items
