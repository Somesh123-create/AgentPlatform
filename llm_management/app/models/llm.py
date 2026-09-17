from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class LLMStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"

class CredentialStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    VALID = "VALID"
    INVALID = "INVALID"

class ConnectionTestStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"

class LLMProvider(Base):
    __tablename__ = "llm_providers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_family: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[LLMStatus] = mapped_column(SQLEnum(LLMStatus), default=LLMStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class LLMModel(Base):
    __tablename__ = "llm_models"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("llm_providers.id", ondelete="CASCADE"), index=True)
    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[LLMStatus] = mapped_column(SQLEnum(LLMStatus), default=LLMStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("provider_id", "model_name", name="uq_llm_provider_model"),)

class LLMModelAccess(Base):
    __tablename__ = "llm_model_access"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_test_status: Mapped[ConnectionTestStatus] = mapped_column(SQLEnum(ConnectionTestStatus), default=ConnectionTestStatus.UNKNOWN, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    __table_args__ = (UniqueConstraint("owner_id", "model_id", name="uq_llm_owner_model"),)

class LLMProviderCredential(Base):
    __tablename__ = "llm_provider_credentials"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CredentialStatus] = mapped_column(SQLEnum(CredentialStatus), default=CredentialStatus.UNKNOWN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("owner_id", "provider_id", name="uq_llm_owner_provider_credential"),)
