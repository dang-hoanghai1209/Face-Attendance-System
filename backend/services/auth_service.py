import base64
import hashlib
import hmac
import json
import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import get_db
from models.user import User


JWT_ALGORITHM = "HS256"
VALID_ROLES = {"admin", "teacher", "viewer"}
security = HTTPBearer(auto_error=False)
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def _secret_key():
    value = os.getenv("SECRET_KEY")
    if not value or value == "replace_me":
        load_dotenv(ENV_PATH, override=True)
        value = os.getenv("SECRET_KEY")
    if not value or value == "replace_me":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY is not configured. Set a strong SECRET_KEY in backend/.env and restart the backend.",
        )
    return value.encode("utf-8")


def _token_expire_minutes():
    raw_value = os.getenv("JWT_EXPIRE_MINUTES")
    if not raw_value:
        load_dotenv(ENV_PATH, override=True)
        raw_value = os.getenv("JWT_EXPIRE_MINUTES")
    if not raw_value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_EXPIRE_MINUTES is not configured. Set it in backend/.env.",
        )
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_EXPIRE_MINUTES must be an integer.",
        ) from exc
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_EXPIRE_MINUTES must be greater than 0.",
        )
    return value


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 240_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 240_000).hex()
    return hmac.compare_digest(digest, expected)


def create_access_token(user: User, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (expires_delta or timedelta(minutes=_token_expire_minutes()))
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(_secret_key(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(_secret_key(), signing_input.encode("ascii"), hashlib.sha256).digest()
        actual_signature = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid token signature.")

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("Token expired.")
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive or no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role is not allowed.")
    return user


def require_role(*roles: str):
    allowed_roles = set(roles)
    invalid_roles = allowed_roles - VALID_ROLES
    if invalid_roles:
        raise ValueError(f"Invalid role(s): {', '.join(sorted(invalid_roles))}")

    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(sorted(allowed_roles))}.",
            )
        return current_user

    return dependency


require_admin = require_role("admin")


def bootstrap_admin_user(db: Session):
    if db.query(User).count() > 0:
        return

    username = os.getenv("AUTH_BOOTSTRAP_ADMIN_USERNAME")
    password = os.getenv("AUTH_BOOTSTRAP_ADMIN_PASSWORD")
    full_name = os.getenv("AUTH_BOOTSTRAP_ADMIN_NAME", "Administrator")
    if not username or not password:
        warnings.warn(
            "No users exist and AUTH_BOOTSTRAP_ADMIN_USERNAME/AUTH_BOOTSTRAP_ADMIN_PASSWORD are not configured. "
            "Skipping admin bootstrap.",
            RuntimeWarning,
        )
        return
    if os.getenv("APP_ENV", "").lower() == "production" and len(password) < 12:
        raise RuntimeError("AUTH_BOOTSTRAP_ADMIN_PASSWORD is too weak for production.")

    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role="admin",
            is_active=True,
        )
    )
    db.commit()
