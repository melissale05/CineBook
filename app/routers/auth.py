"""
Authentication routes: login, register, logout, current user.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional

from passlib.context import CryptContext

from app.db.connection import get_db
from app.sessions import create_session, delete_session
from app.dependencies import get_current_user

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    favorite_genre: Optional[str] = None


def _user_row_to_dict(row) -> dict:
    return {
        "user_id": row["userid"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "favorite_genre": row.get("favoritegenre"),
        "loyalty_points": row.get("loyaltypoints", 0),
    }


@router.post("/login")
def login(body: LoginRequest):
    with get_db() as cur:
        cur.execute(
            "SELECT UserID, Name, Email, Password, Role, FavoriteGenre, LoyaltyPoints "
            "FROM Users WHERE Email = %s",
            (body.email,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not pwd_context.verify(body.password, row["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = _user_row_to_dict(row)
    token = create_session(user)
    return {"token": token, **user}


@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    hashed = pwd_context.hash(body.password)
    with get_db() as cur:
        cur.execute("SELECT UserID FROM Users WHERE Email = %s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        cur.execute(
            """
            INSERT INTO Users (Name, Email, Password, Role, FavoriteGenre, LoyaltyPoints)
            VALUES (%s, %s, %s, 'customer', %s, 0)
            RETURNING UserID, Name, Email, Role, FavoriteGenre, LoyaltyPoints
            """,
            (body.name, body.email, hashed, body.favorite_genre),
        )
        row = cur.fetchone()

    user = _user_row_to_dict(row)
    token = create_session(user)
    return {"token": token, **user}


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    return {"message": "Logged out"}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
