from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.instance_type import InstanceType
    from app.models.region import Region


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text(), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(Text(), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    regions: Mapped[list["Region"]] = relationship(
        "Region", back_populates="provider", lazy="selectin"
    )
    instance_types: Mapped[list["InstanceType"]] = relationship(
        "InstanceType", back_populates="provider", lazy="selectin"
    )
