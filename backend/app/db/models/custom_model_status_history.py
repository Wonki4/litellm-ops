import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import CustomBase
from app.db.models.custom_model_catalog import ModelStatus


class CustomModelStatusHistory(CustomBase):
    """Immutable audit log for model catalog status changes.

    A row is created whenever a catalog entry's status changes,
    including the initial creation.
    """

    __tablename__ = "custom_model_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_model_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    previous_status: Mapped[ModelStatus | None] = mapped_column(
        Enum(
            ModelStatus,
            name="custom_model_status",
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    new_status: Mapped[ModelStatus] = mapped_column(
        Enum(
            ModelStatus,
            name="custom_model_status",
            create_constraint=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
