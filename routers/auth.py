from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from dependencies import DbSession
from models import User, normalize_email
from schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse
from security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession):
    email_taken = HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
    )

    # Checking first skips the slow password hash for an email that's taken.
    existing_id = db.scalar(select(User.id).where(User.email == normalize_email(payload.email)))
    if existing_id is not None:
        raise email_taken

    user = User(
        email=payload.email,
        fullname=payload.fullname,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two signups with the same email can both pass the check above.
        db.rollback()
        raise email_taken
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.execute(
        select(User.id, User.password_hash).where(User.email == normalize_email(payload.email))
    ).one_or_none()

    # Always run the hash check so a missing email isn't faster than a wrong password.
    password_ok = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user.id))
