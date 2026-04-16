"""
In-memory session store.
Maps token (UUID string) → {user_id, email, name, role, favorite_genre, loyalty_points}
Fine for a class demo; replace with Redis/DB tokens for production.
"""
import uuid
from typing import Optional

_sessions: dict[str, dict] = {}


def create_session(user: dict) -> str:
    token = str(uuid.uuid4())
    _sessions[token] = user
    return token


def get_session(token: str) -> Optional[dict]:
    return _sessions.get(token)


def delete_session(token: str) -> None:
    _sessions.pop(token, None)
