from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.instance_type import InstanceType
    from app.models.region import Region


class InstancePricing(Base):
    __tablename__ = "instance_pricing"
    __table_args__ = (
        UniqueConstraint(
            "instance_type_id", "region_id", "pricing_model",
            name="uq_instance_pricing_type_region_model",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instance_type_id: Mapped[int] = mapped_column(
        ForeignKey("instance_types.id", ondelete="CASCADE"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False
    )
    pricing_model: Mapped[str] = mapped_column(Text(), nullable=False)
    hourly_price_usd: Mapped[float] = mapped_column(Float(), nullable=False)
    monthly_price_usd: Mapped[float] = mapped_column(Float(), nullable=False)
    currency: Mapped[str] = mapped_column(Text(), nullable=False, default="USD")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instance_type: Mapped["InstanceType"] = relationship(
        "InstanceType", back_populates="instance_pricings"
    )
    region: Mapped["Region"] = relationship(
        "Region", back_populates="instance_pricings"
    )
