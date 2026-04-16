<<<<<<< HEAD
"""
CineBook — FastAPI entry point.
Run with:  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.routers import auth, movies, showtimes, bookings, recommendations, admin

app = FastAPI(
    title="CineBook API",
    description="Movie Theater Management & Ticket Booking System",
    version="1.0.0",
)

# Allow all origins for local demo (frontend served from file:// or a different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router,            prefix="/api/auth",            tags=["auth"])
app.include_router(movies.router,          prefix="/api/movies",          tags=["movies"])
app.include_router(showtimes.router,       prefix="/api/showtimes",       tags=["showtimes"])
app.include_router(bookings.router,        prefix="/api/bookings",        tags=["bookings"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(admin.router,           prefix="/api/admin",           tags=["admin"])


@app.get("/health")
def health():
    return {"status": "ok", "app": "CineBook"}


# Serve the HTML frontend from /ui/*
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "CineBook_Frontend")
frontend_dir = os.path.abspath(frontend_dir)

if os.path.isdir(frontend_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(frontend_dir, "homepage.html"))
=======
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
>>>>>>> ef8d6d0562c39a4fe5763bcdc0238f89f32e0f48
