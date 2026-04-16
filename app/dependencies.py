"""
Shared FastAPI dependencies: authentication & role enforcement.
"""
from fastapi import Header, HTTPException, status
from typing import Optional

from app.sessions import get_session


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Extract and validate Bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = authorization[7:]
    user = get_session(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token",
        )
    return user


def require_admin(current_user: dict = None) -> dict:
    """Raises 403 if the current user is not an admin."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
