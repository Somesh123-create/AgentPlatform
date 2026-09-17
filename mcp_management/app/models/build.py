from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, ForeignKeyConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPBuildStatus(str, Enum):
    QUEUED = "QUEUED"
    BUILDING = "BUILDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class MCPBuild(Base):
    __tablename__ = "mcp_builds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mcp_id", "version_id"],
            ["mcp_versions.mcp_id", "mcp_versions.id"],
            name="fk_mcp_builds_mcp_version",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mcp_id: Mapped[int] = mapped_column(ForeignKey("mcps.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[MCPBuildStatus] = mapped_column(SQLEnum(MCPBuildStatus), default=MCPBuildStatus.QUEUED, index=True)
    image_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)