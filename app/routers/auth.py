<<<<<<< HEAD
"""
Authentication routes: login, register, logout, current user.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
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
        # Check duplicate
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
def logout(authorization: str = None, current_user: dict = Depends(get_current_user)):
    # token is available through the header; we just clear the session
    # We can't easily get the raw token here without extra work, so just return ok
    return {"message": "Logged out"}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
=======
from fastapi import APIRouter, HTTPException
from app.db.connection import get_db
import bcrypt

router = APIRouter()


@router.post("/register")
def register(name: str, email: str, password: str):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with get_db() as cur:
        try:
            cur.execute("""
                INSERT INTO Users (Name, Email, Password)
                VALUES (%s, %s, %s)
                RETURNING UserID
            """, (name, email, hashed))

            user = cur.fetchone()
            return {"message": "User created", "user_id": user["userid"]}
        except Exception:
            raise HTTPException(status_code=400, detail="Email already exists")


@router.post("/login")
def login(email: str, password: str):
    with get_db() as cur:
        cur.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cur.fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not bcrypt.checkpw(password.encode(), user["password"].encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return {
            "message": "Login successful",
            "user_id": user["userid"],
            "role": user["role"]
        }
>>>>>>> ef8d6d0562c39a4fe5763bcdc0238f89f32e0f48
