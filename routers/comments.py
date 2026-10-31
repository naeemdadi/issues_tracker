from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from dependencies import CurrentUser, DbSession, IssueForMember, PageParams
from models import Comment
from schemas import CommentCreate, CommentResponse

router = APIRouter(prefix="/api/issues/{issue_id}/comments", tags=["comments"])

@router.get("", response_model=list[CommentResponse])
def get_comments(access: IssueForMember, page: PageParams, db: DbSession):
    comments = db.scalars(
        select(Comment)
        .where(Comment.issue_id == access.issue.id)
        .options(joinedload(Comment.author))
        .order_by(Comment.created_at, Comment.id)
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    return [CommentResponse.model_validate(comment) for comment in comments]

@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(payload: CommentCreate, access: IssueForMember, current_user: CurrentUser, db: DbSession):
    comment = Comment(issue=access.issue, author=current_user, text=payload.text)
    db.add(comment)
    db.commit()
    return CommentResponse.model_validate(comment)
