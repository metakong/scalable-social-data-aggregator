from __future__ import annotations
import datetime
import enum
from typing import Any
from sqlalchemy import DateTime, Enum as DBEnum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .extensions import db

class IdeaStatus(enum.Enum):
    PENDING_CSO_VETTING = "PENDING_CSO_VETTING"
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    APPROVED_FOR_DEV = "APPROVED_FOR_DEV"
    PUBLISHED = "PUBLISHED"

class AppIdea(db.Model):
    __tablename__ = 'app_ideas'

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[IdeaStatus] = mapped_column(
        DBEnum(IdeaStatus, name="ideastatus"),
        default=IdeaStatus.PENDING_ANALYSIS,
        index=True
    )
    apk_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AI-Generated Fields
    ai_generated_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_generated_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    competition_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    swot_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the object to a dictionary."""
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "status": self.status.value,
            "ai_title": self.ai_generated_title,
            "ai_summary": self.ai_generated_summary,
            "competition_analysis": self.competition_analysis,
            "swot_analysis": self.swot_analysis,
            "created_at": self.created_at.isoformat(),
        }