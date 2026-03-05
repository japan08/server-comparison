from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.instance_pricing import InstancePricing
    from app.models.provider import Provider


class Region(Base):
    __tablename__ = "regions"
    __table_args__ = (UniqueConstraint("provider_id", "region_code", name="uq_regions_provider_region"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    region_code: Mapped[str] = mapped_column(Text(), nullable=False)
    region_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    country: Mapped[str | None] = mapped_column(Text(), nullable=True)
    continent: Mapped[str | None] = mapped_column(Text(), nullable=True)

    provider: Mapped["Provider"] = relationship("Provider", back_populates="regions")
    instance_pricings: Mapped[list["InstancePricing"]] = relationship(
        "InstancePricing", back_populates="region", lazy="selectin"
    )
