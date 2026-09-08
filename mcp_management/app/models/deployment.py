from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPDeploymentStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class MCPDeployment(Base):
    __tablename__ = "mcp_deployments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mcp_id: Mapped[int] = mapped_column(ForeignKey("mcps.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("mcp_versions.id", ondelete="CASCADE"), index=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("mcp_builds.id", ondelete="CASCADE"), index=True)
    status: Mapped[MCPDeploymentStatus] = mapped_column(SQLEnum(MCPDeploymentStatus), default=MCPDeploymentStatus.STARTING, index=True)
    container_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_ref: Mapped[str] = mapped_column(Text, nullable=False)
    logs: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)