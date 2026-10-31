import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Issue, Label, MembershipStatus, ProjectRole, User, UserProject
from security import decode_access_token

DbSession = Annotated[Session, Depends(get_db)]

# auto_error=False so a missing header reaches our own 401 below.
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    not_authenticated = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise not_authenticated

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise not_authenticated
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

def find_membership(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> Optional[UserProject]:
    return db.scalar(
        select(UserProject)
        .options(joinedload(UserProject.project))
        .where(
            UserProject.project_id == project_id,
            UserProject.user_id == user_id,
            UserProject.status == MembershipStatus.ACCEPTED,
        )
    )

def ensure_owner(membership: UserProject) -> None:
    if membership.role != ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the project owner can do this"
        )

def get_project_membership(project_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> UserProject:
    membership = find_membership(db, project_id, current_user.id)
    # 404 rather than 403 so non-members can't tell the project exists.
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return membership

ProjectMembership = Annotated[UserProject, Depends(get_project_membership)]

def require_project_owner(membership: ProjectMembership) -> UserProject:
    ensure_owner(membership)
    return membership

ProjectOwnership = Annotated[UserProject, Depends(require_project_owner)]

@dataclass
class IssueAccess:
    issue: Issue
    membership: UserProject

def get_issue_access(issue_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> IssueAccess:
    issue = db.get(Issue, issue_id)
    membership = find_membership(db, issue.project_id, current_user.id) if issue else None
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return IssueAccess(issue=issue, membership=membership)

IssueForMember = Annotated[IssueAccess, Depends(get_issue_access)]

def require_label_owner(label_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Label:
    label = db.get(Label, label_id)
    membership = find_membership(db, label.project_id, current_user.id) if label else None
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    ensure_owner(membership)
    return label

OwnedLabel = Annotated[Label, Depends(require_label_owner)]

@dataclass
class Pagination:
    limit: int
    offset: int

def get_pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)

PageParams = Annotated[Pagination, Depends(get_pagination)]
