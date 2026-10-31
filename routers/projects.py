from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import contains_eager

from dependencies import CurrentUser, DbSession, ProjectMembership, ProjectOwnership
from models import (
    Issue,
    IssueStatus,
    Label,
    MembershipStatus,
    Project,
    ProjectRole,
    UserProject,
    issue_labels,
)
from schemas import (
    LabelCount,
    ProjectCreate,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
)

STARTER_LABELS = ("bug", "feature")
TOP_LABELS_LIMIT = 5

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=list[ProjectResponse])
def get_my_projects(current_user: CurrentUser, db: DbSession):
    memberships = db.scalars(
        select(UserProject)
        .join(UserProject.project)
        # Fills membership.project from the join above instead of joining again.
        .options(contains_eager(UserProject.project))
        .where(
            UserProject.user_id == current_user.id,
            UserProject.status != MembershipStatus.REMOVED,
        )
        .order_by(Project.created_at.desc())
    ).all()
    return [ProjectResponse.from_membership(membership) for membership in memberships]

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, current_user: CurrentUser, db: DbSession):
    project = Project(name=payload.name)
    owner = UserProject(
        user=current_user, role=ProjectRole.OWNER, status=MembershipStatus.ACCEPTED
    )
    project.memberships.append(owner)
    project.labels = [Label(name=name) for name in STARTER_LABELS]
    db.add(project)
    db.commit()
    return ProjectResponse.from_membership(owner)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(membership: ProjectMembership):
    return ProjectResponse.from_membership(membership)

@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(payload: ProjectUpdate, ownership: ProjectOwnership, db: DbSession):
    ownership.project.name = payload.name
    db.commit()
    return ProjectResponse.from_membership(ownership)

@router.get("/{project_id}/summary", response_model=ProjectSummaryResponse)
def get_project_summary(membership: ProjectMembership, db: DbSession):
    project_id = membership.project_id
    status_counts = dict(
        db.execute(
            select(Issue.status, func.count())
            .where(Issue.project_id == project_id)
            .group_by(Issue.status)
        ).all()
    )

    issue_count = func.count(issue_labels.c.issue_id).label("issue_count")
    top_labels = db.execute(
        select(Label.id, Label.name, issue_count)
        .join(issue_labels, issue_labels.c.label_id == Label.id)
        .where(Label.project_id == project_id)
        .group_by(Label.id, Label.name)
        .order_by(issue_count.desc(), Label.name)
        .limit(TOP_LABELS_LIMIT)
    ).all()

    return ProjectSummaryResponse(
        open_issues=status_counts.get(IssueStatus.OPEN, 0),
        closed_issues=status_counts.get(IssueStatus.CLOSED, 0),
        top_labels=[LabelCount(id=row.id, name=row.name, issue_count=row.issue_count) for row in top_labels],
    )
