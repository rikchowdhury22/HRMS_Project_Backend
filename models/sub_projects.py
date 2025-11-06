from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

SCHEMA = "dbo"

class SubProject(Base):
    __tablename__ = "sub_projects"
    __table_args__ = {"schema": SCHEMA}

    subproject_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.projects.project_id", ondelete="CASCADE"),
        nullable=False
    )

    assigned_by: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.user_id"), nullable=False
    )

    assigned_to: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.user_id"), nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    project_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    # ✅ Tell SQLAlchemy that DB handles timestamps
    created_on: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )

    last_modified: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
        onupdate=datetime.utcnow  # optional, only affects ORM side
    )
