import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pwdlib import PasswordHash

from config import settings

JWT_ALGORITHM = "HS256"

password_hasher = PasswordHash.recommended()

# Checked against when the email doesn't exist, so that case takes as long
# as a wrong password and response times don't reveal which emails exist.
DUMMY_HASH = password_hasher.hash("dummy-password")

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)

def create_access_token(user_id: uuid.UUID) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[uuid.UUID]:
    # None covers every bad case: wrong signature, expired, or a malformed sub.
    try:
        claims = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[JWT_ALGORITHM])
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
