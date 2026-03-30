from fastapi import FastAPI
from app.routers import auth, movies, bookings, admin

app = FastAPI(title="CineBook API")

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(movies.router, prefix="/movies", tags=["Movies"])
app.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


@app.get("/")
def root():
    return {"message": "CineBook API is running"}
