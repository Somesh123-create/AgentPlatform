from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentFramework(str, Enum):
    GOOGLE_ADK = "GOOGLE_ADK"
    LANGGRAPH = "LANGGRAPH"


class AgentDraftStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"


class AgentDraft(Base):
    __tablename__ = "agent_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    framework: Mapped[AgentFramework] = mapped_column(SQLEnum(AgentFramework), nullable=False)
    mcp_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mcp_version_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mcp_version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    llm_model_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    llm_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    llm_model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_directory: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    mcp_connections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    project_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    default_build_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    files: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[AgentDraftStatus] = mapped_column(SQLEnum(AgentDraftStatus), default=AgentDraftStatus.DRAFT, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
