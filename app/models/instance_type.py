from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.instance_pricing import InstancePricing
    from app.models.provider import Provider


class InstanceType(Base):
    __tablename__ = "instance_types"
    __table_args__ = (
        UniqueConstraint("provider_id", "instance_name", name="uq_instance_types_provider_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    instance_name: Mapped[str] = mapped_column(Text(), nullable=False)
    family: Mapped[str | None] = mapped_column(Text(), nullable=True)
    vcpu: Mapped[int] = mapped_column(Integer(), nullable=False)
    ram_gb: Mapped[float] = mapped_column(Float(), nullable=False)
    storage_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    storage_gb: Mapped[float] = mapped_column(Float(), nullable=False)
    gpu_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    gpu_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    network_performance: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    provider: Mapped["Provider"] = relationship("Provider", back_populates="instance_types")
    instance_pricings: Mapped[list["InstancePricing"]] = relationship(
        "InstancePricing", back_populates="instance_type", lazy="selectin"
    )
