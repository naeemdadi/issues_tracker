import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager

from dependencies import CurrentUser, DbSession, ProjectMembership, ProjectOwnership
from models import MembershipStatus, ProjectRole, User, UserProject, normalize_email
from schemas import InviteRequest, MemberResponse, ProjectResponse

router = APIRouter(prefix="/api/projects/{project_id}/members", tags=["members"])

@router.get("", response_model=list[MemberResponse])
def get_members(membership: ProjectMembership, db: DbSession):
    members = db.scalars(
        select(UserProject)
        .join(UserProject.user)
        .options(contains_eager(UserProject.user))
        .where(
            UserProject.project_id == membership.project_id,
            UserProject.status != MembershipStatus.REMOVED,
        )
        .order_by(UserProject.created_at)
    ).all()
    return [MemberResponse.model_validate(member) for member in members]

@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def invite_member(payload: InviteRequest, ownership: ProjectOwnership, db: DbSession):
    already_in_project = HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail="User is already a member or invited"
    )

    invitee = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if invitee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with that email")

    membership = db.scalar(
        select(UserProject).where(
            UserProject.project_id == ownership.project_id,
            UserProject.user_id == invitee.id,
        )
    )
    if membership is None:
        membership = UserProject(project_id=ownership.project_id, user=invitee)
        db.add(membership)
    elif membership.status == MembershipStatus.REMOVED:
        # The unique user + project pair means re-inviting reuses the old row.
        membership.status = MembershipStatus.INVITED
        membership.role = ProjectRole.MEMBER
    else:
        raise already_in_project

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise already_in_project
    return MemberResponse.model_validate(membership)

@router.post("/accept", response_model=ProjectResponse)
def accept_invite(project_id: uuid.UUID, current_user: CurrentUser, db: DbSession):
    # Can't use ProjectMembership here: it only lets ACCEPTED members through.
    membership = db.scalar(
        select(UserProject).where(
            UserProject.project_id == project_id,
            UserProject.user_id == current_user.id,
            UserProject.status == MembershipStatus.INVITED,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invite")

    membership.status = MembershipStatus.ACCEPTED
    db.commit()
    return ProjectResponse.from_membership(membership)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: uuid.UUID, ownership: ProjectOwnership, db: DbSession):
    member = db.scalar(
        select(UserProject).where(
            UserProject.project_id == ownership.project_id,
            UserProject.user_id == user_id,
            UserProject.status != MembershipStatus.REMOVED,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.role == ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The project owner can't be removed"
        )

    # Also cancels a pending invite, since INVITED rows land here too.
    member.status = MembershipStatus.REMOVED
    db.commit()
