from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {
        "schema": "dbo",
        "implicit_returning": False,   # ✅ place it here, not in __mapper_args__
    }

    project_id     = Column(Integer, primary_key=True, autoincrement=True)
    project_name   = Column(String, nullable=False)
    description    = Column(String)
    project_status = Column(String, nullable=False)
    created_by     = Column(Integer, nullable=False)
    created_on     = Column(
        DateTime,
        nullable=False,
        server_default=func.sysutcdatetime()
    )
    last_modified  = Column(
        DateTime,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime()
    )

    members = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    subprojects = relationship(
        "SubProject",
        back_populates="project",
        lazy="selectin",          # efficient, 1 extra query per collection
        cascade="all, delete-orphan"
    )
