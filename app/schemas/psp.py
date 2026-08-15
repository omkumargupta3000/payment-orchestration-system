from pydantic import BaseModel, ConfigDict, Field


class PSPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    success_rate: float
    avg_latency_ms: int
    is_active: bool


class PSPUpdateRequest(BaseModel):
    """Used by the demo panel on the dashboard to tweak PSP behaviour."""
    success_rate: float | None = Field(default=None, ge=0, le=1)
    avg_latency_ms: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
