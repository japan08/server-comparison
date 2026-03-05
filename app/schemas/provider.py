from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProviderBase(BaseModel):
    name: str
    slug: str
    website: str | None = None


class ProviderCreate(ProviderBase):
    pass


class ProviderRead(ProviderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
