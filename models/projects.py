from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {
        "schema": "dbo",
        "implicit_returning": False,
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

    # 🔹 renamed relationship
    project_members = relationship(
        "ProjectMember",
        back_populates="project_members",
        cascade="all, delete-orphan",
    )

    subprojects = relationship(
        "SubProject",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )