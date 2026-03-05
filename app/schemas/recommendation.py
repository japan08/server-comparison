from pydantic import BaseModel, Field, model_validator


class RecommendRequest(BaseModel):
    query: str | None = Field(
        None,
        min_length=1,
        description="Natural language request (e.g. '4 vCPUs, 16GB RAM in Europe, max $100/month'). If set, overrides structured fields.",
    )
    cpu: int | None = Field(None, ge=1, description="Minimum vCPUs (required if query not set)")
    ram: float | None = Field(None, ge=0.1, description="Minimum RAM in GB (required if query not set)")
    budget: float | None = Field(None, ge=0, description="Maximum monthly budget in USD (required if query not set)")
    region: str | None = Field(None, min_length=1, description="Continent or region name (e.g. Europe). Required if query not set.")
    include_explanation: bool = Field(False, description="Ask Ollama for a one-sentence explanation of the recommendations")

    @model_validator(mode="after")
    def require_structured_or_query(self) -> "RecommendRequest":
        if self.query:
            return self
        if self.cpu is None or self.ram is None or self.budget is None or self.region is None:
            raise ValueError("Either 'query' or all of (cpu, ram, budget, region) must be provided")
        return self


class RecommendationItem(BaseModel):
    provider: str
    instance: str
    vcpu: int
    ram: float
    price_monthly: float


class RecommendResponse(BaseModel):
    recommendations: list[RecommendationItem]
    explanation: str | None = None
