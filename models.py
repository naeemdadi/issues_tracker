import enum
import uuid
from datetime import datetime
from typing import List
from typing import Optional
from sqlalchemy import Column, ForeignKey, Index, MetaData, Table, UniqueConstraint
from sqlalchemy import DateTime, String, Text
from sqlalchemy import func, text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates

class ProjectRole(str, enum.Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"

class MembershipStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    REMOVED = "REMOVED"

class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

# Stops "A@x.com" and "a@x.com" from becoming two separate accounts.
def normalize_email(email: str) -> str:
    return email.strip().lower()

class Base(DeclarativeBase):
    # Gives unnamed constraints predictable names so Alembic can find them later.
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fullname: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    memberships: Mapped[List["UserProject"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        return normalize_email(email)

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, fullname={self.fullname!r})"

class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))

    memberships: Mapped[List["UserProject"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    issues: Mapped[List["Issue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    labels: Mapped[List["Label"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

class UserProject(TimestampMixin, Base):
    __tablename__ = "user_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MembershipStatus] = mapped_column(default=MembershipStatus.INVITED)
    role: Mapped[ProjectRole] = mapped_column(default=ProjectRole.MEMBER)

    user: Mapped["User"] = relationship(back_populates="memberships")
    project: Mapped["Project"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_per_project"),
        # Enum columns store the member name, so 'OWNER' matches ProjectRole.OWNER.
        Index(
            "uq_one_owner_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("role = 'OWNER'"),
        ),
    )

issue_labels = Table(
    "issue_labels",
    Base.metadata,
    Column("issue_id", ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True, index=True),
)

class Label(Base):
    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    project: Mapped["Project"] = relationship(back_populates="labels")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_label_name_per_project"),
    )

class Issue(TimestampMixin, Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[IssueStatus] = mapped_column(default=IssueStatus.OPEN)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    project: Mapped["Project"] = relationship(back_populates="issues")
    author: Mapped["User"] = relationship()
    labels: Mapped[List["Label"]] = relationship(secondary=issue_labels)
    comments: Mapped[List["Comment"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_issues_project_status", "project_id", "status"),
    )

class Comment(TimestampMixin, Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    issue: Mapped["Issue"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship()
