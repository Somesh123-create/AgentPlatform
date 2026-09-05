from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPType(str, Enum):
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"


class MCPProtocol(str, Enum):
    STDIO = "STDIO"
    SSE = "SSE"
    STREAMABLE_HTTP = "STREAMABLE_HTTP"


class MCPAccess(str, Enum):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class MCPStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MCP(Base):

    __tablename__ = "mcps"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    owner_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    mcp_type: Mapped[MCPType] = mapped_column(
        SQLEnum(MCPType),
        nullable=False,
    )

    protocol: Mapped[MCPProtocol] = mapped_column(
        SQLEnum(MCPProtocol),
        nullable=False,
    )

    access: Mapped[MCPAccess] = mapped_column(
        SQLEnum(MCPAccess),
        nullable=False,
        default=MCPAccess.PRIVATE,
    )

    status: Mapped[MCPStatus] = mapped_column(
        SQLEnum(MCPStatus),
        nullable=False,
        default=MCPStatus.DRAFT,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
