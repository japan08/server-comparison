from pydantic import BaseModel, ConfigDict


class InstanceTypeBase(BaseModel):
    instance_name: str
    family: str | None = None
    vcpu: int
    ram_gb: float
    storage_type: str | None = None
    storage_gb: float
    gpu_type: str | None = None
    gpu_count: int = 0
    network_performance: str | None = None
    is_active: bool = True


class InstancePricingBase(BaseModel):
    pricing_model: str
    hourly_price_usd: float
    monthly_price_usd: float
    currency: str = "USD"


class InstanceTypeRead(InstanceTypeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int


class InstancePricingRead(InstancePricingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instance_type_id: int
    region_id: int
