import asyncio
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from dependencies import CurrentUser, DbSession, IssueForMember, PageParams, ProjectMembership
from models import Issue, IssueStatus, Label, ProjectRole
from schemas import IssueCreate, IssueResponse, IssueUpdate

STREAM_WORD_DELAY_SECONDS = 0.1

router = APIRouter(prefix="/api", tags=["issues"])

def load_project_labels(db: Session, project_id: uuid.UUID, label_ids: list[uuid.UUID]) -> list[Label]:
    unique_ids = set(label_ids)
    labels = db.scalars(
        select(Label).where(Label.project_id == project_id, Label.id.in_(unique_ids))
    ).all()
    # Fewer matches means an id is unknown or belongs to another project.
    if len(labels) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more labels don't belong to this project",
        )
    return list(labels)

@router.get("/projects/{project_id}/issues", response_model=list[IssueResponse])
def get_issues(
    membership: ProjectMembership,
    page: PageParams,
    db: DbSession,
    # Named status_filter so it doesn't shadow fastapi's status module.
    status_filter: Annotated[Optional[IssueStatus], Query(alias="status")] = None,
    label_id: Optional[uuid.UUID] = None,
):
    query = (
        select(Issue)
        .where(Issue.project_id == membership.project_id)
        .options(joinedload(Issue.author), selectinload(Issue.labels))
        # id breaks ties between issues created in the same second.
        .order_by(Issue.created_at.desc(), Issue.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    if status_filter is not None:
        query = query.where(Issue.status == status_filter)
    if label_id is not None:
        query = query.where(Issue.labels.any(Label.id == label_id))

    issues = db.scalars(query).all()
    return [IssueResponse.model_validate(issue) for issue in issues]

@router.post(
    "/projects/{project_id}/issues",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issue(payload: IssueCreate, membership: ProjectMembership, current_user: CurrentUser, db: DbSession):
    issue = Issue(
        project_id=membership.project_id,
        author=current_user,
        title=payload.title,
        description=payload.description,
        labels=load_project_labels(db, membership.project_id, payload.label_ids),
    )
    db.add(issue)
    db.commit()
    return IssueResponse.model_validate(issue)

@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_issue(access: IssueForMember):
    return IssueResponse.model_validate(access.issue)

@router.patch("/issues/{issue_id}", response_model=IssueResponse)
def update_issue(payload: IssueUpdate, access: IssueForMember, db: DbSession):
    issue, membership = access.issue, access.membership
    is_author = issue.author_id == membership.user_id
    if not (is_author or membership.role == ProjectRole.OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the issue author or the project owner can edit this issue",
        )

    if payload.title is not None:
        issue.title = payload.title
    if payload.description is not None:
        issue.description = payload.description
    if payload.label_ids is not None:
        issue.labels = load_project_labels(db, issue.project_id, payload.label_ids)
    if payload.status is not None and payload.status != issue.status:
        issue.status = payload.status
        issue.closed_at = datetime.now(timezone.utc) if payload.status == IssueStatus.CLOSED else None

    db.commit()
    return IssueResponse.model_validate(issue)

def fake_issue_summary(issue: Issue) -> str:
    state = "still open" if issue.status == IssueStatus.OPEN else "closed"
    return (
        f'This issue, "{issue.title}", is {state}. '
        "A real AI summary of the discussion will replace this placeholder text later."
    )

@router.get("/issues/{issue_id}/summary/stream")
async def stream_issue_summary(access: IssueForMember):
    # Built here, before streaming starts, so the generator never touches the DB.
    words = fake_issue_summary(access.issue).split()

    async def word_stream():
        for word in words:
            yield f"{word} "
            await asyncio.sleep(STREAM_WORD_DELAY_SECONDS)

    return StreamingResponse(word_stream(), media_type="text/plain")
