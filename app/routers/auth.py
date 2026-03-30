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
