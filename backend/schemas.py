from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# Each class maps to a collection with its lowercase name


class API(BaseModel):
    name: str = Field(..., description="Human-readable name, e.g., 'OpenAI'")
    provider: Optional[str] = Field(None, description="Provider or vendor name")
    # Rate limit window in seconds and max requests allowed in that window
    window_seconds: int = Field(..., gt=0)
    max_requests: int = Field(..., gt=0)
    # Optional per-endpoint overrides
    endpoints: Optional[List[str]] = Field(None, description="List of tracked endpoints identifiers")
    thresholds: List[int] = Field(default_factory=lambda: [80, 90, 95], description="Alert thresholds in percent")


class APIOut(API):
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class UsageEvent(BaseModel):
    api_id: str = Field(..., description="Reference to API (_id as string)")
    endpoint: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # number of requests consumed by this event (often 1, but can be batched)
    units: int = Field(default=1, gt=0)


class PredictedStatus(BaseModel):
    api_id: str
    window_seconds: int
    max_requests: int
    current_count: int
    utilization_percent: float
    projected_hit_in_seconds: Optional[int] = None
    thresholds_crossed: List[int] = []
