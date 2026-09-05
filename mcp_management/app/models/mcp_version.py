from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPSourceKind(str, Enum):
    ZIP = "ZIP"
    GIT = "GIT"


class MCPVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    BUILDING = "BUILDING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class MCPVersion(Base):
    __tablename__ = "mcp_versions"
    __table_args__ = (
        UniqueConstraint("mcp_id", "version", name="uq_mcp_versions_mcp_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mcp_id: Mapped[int] = mapped_column(
        ForeignKey("mcps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[MCPSourceKind] = mapped_column(SQLEnum(MCPSourceKind), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    manifest: Mapped[str] = mapped_column(Text, nullable=False)
    image_reference: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    image_digest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MCPVersionStatus] = mapped_column(
        SQLEnum(MCPVersionStatus),
        nullable=False,
        default=MCPVersionStatus.DRAFT,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)