from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

SCHEMA = "dbo"

class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="PK_project_members"),
        {"schema": SCHEMA},
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.projects.project_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    designation_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.designation_list.designation_id"),
        nullable=True,
    )

    # ✅ Important: give BOTH a Python-side default and a DB-side server default
    added_on: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,            # client-side: SQLAlchemy fills if you forget
        server_default=func.sysutcdatetime()  # server-side: SQL Server fills if ORM omits
    )

    project_members = relationship("Project", back_populates="project_members")
