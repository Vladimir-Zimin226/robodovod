"""Additive version documents; organizer rows and historical runs remain untouched."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from storage_models import Base


class AdminCatalogDocument(Base):
    __tablename__ = "admin_catalog_documents"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_admin_catalog_revision"),
        CheckConstraint(
            "jsonb_typeof(document) = 'object'", name="ck_admin_catalog_document"
        ),
        CheckConstraint(
            "import_sha256 IS NULL OR import_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_admin_catalog_import_sha",
        ),
    )

    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    import_sha256: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
