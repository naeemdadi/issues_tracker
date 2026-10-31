from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from dependencies import DbSession, OwnedLabel, ProjectMembership, ProjectOwnership
from models import Label
from schemas import LabelCreate, LabelResponse, LabelUpdate

router = APIRouter(prefix="/api", tags=["labels"])

label_name_taken = HTTPException(
    status_code=status.HTTP_409_CONFLICT, detail="A label with that name already exists"
)

@router.get("/projects/{project_id}/labels", response_model=list[LabelResponse])
def get_labels(membership: ProjectMembership, db: DbSession):
    labels = db.scalars(
        select(Label).where(Label.project_id == membership.project_id).order_by(Label.name)
    ).all()
    return [LabelResponse.model_validate(label) for label in labels]

@router.post(
    "/projects/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_label(payload: LabelCreate, ownership: ProjectOwnership, db: DbSession):
    label = Label(project_id=ownership.project_id, name=payload.name)
    db.add(label)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise label_name_taken
    return LabelResponse.model_validate(label)

@router.patch("/labels/{label_id}", response_model=LabelResponse)
def update_label(payload: LabelUpdate, label: OwnedLabel, db: DbSession):
    label.name = payload.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise label_name_taken
    return LabelResponse.model_validate(label)

@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(label: OwnedLabel, db: DbSession):
    # ondelete="CASCADE" on issue_labels removes the tag from every issue.
    db.delete(label)
    db.commit()
