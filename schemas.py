import uuid
from datetime import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from models import IssueStatus, MembershipStatus, ProjectRole, UserProject

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LabelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
IssueTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
IssueDescription = Annotated[str, StringConstraints(max_length=10_000)]
CommentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)]

class SignupRequest(BaseModel):
    email: EmailStr
    # The upper cap stops someone posting a huge string to make hashing slow.
    password: str = Field(min_length=8, max_length=128)
    fullname: Optional[str] = Field(default=None, max_length=100)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    fullname: Optional[str]
    created_at: datetime

class ProjectCreate(BaseModel):
    name: ProjectName

class ProjectUpdate(BaseModel):
    name: ProjectName

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
    # The current user's membership, so the client knows which controls to show.
    role: ProjectRole
    status: MembershipStatus

    @classmethod
    def from_membership(cls, membership: UserProject) -> "ProjectResponse":
        project = membership.project
        return cls(
            id=project.id,
            name=project.name,
            created_at=project.created_at,
            updated_at=project.updated_at,
            role=membership.role,
            status=membership.status,
        )

class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    fullname: Optional[str]

class InviteRequest(BaseModel):
    email: EmailStr

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserSummary
    role: ProjectRole
    status: MembershipStatus

class LabelCreate(BaseModel):
    name: LabelName

class LabelUpdate(BaseModel):
    name: LabelName

class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str

class IssueCreate(BaseModel):
    title: IssueTitle
    description: IssueDescription = ""
    label_ids: list[uuid.UUID] = Field(default_factory=list)

class IssueUpdate(BaseModel):
    # None means "not sent". None of these fields can be cleared to null.
    title: Optional[IssueTitle] = None
    description: Optional[IssueDescription] = None
    status: Optional[IssueStatus] = None
    label_ids: Optional[list[uuid.UUID]] = None

class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    status: IssueStatus
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    author: UserSummary
    labels: list[LabelResponse]

class CommentCreate(BaseModel):
    text: CommentText

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    created_at: datetime
    author: UserSummary

class LabelCount(BaseModel):
    id: uuid.UUID
    name: str
    issue_count: int

class ProjectSummaryResponse(BaseModel):
    open_issues: int
    closed_issues: int
    top_labels: list[LabelCount]
