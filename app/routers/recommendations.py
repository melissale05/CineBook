"""
Recommendation route: calls the get_user_recommendations() stored function.
Customer-only endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.db.connection import get_db
from app.dependencies import get_current_user

router = APIRouter()


@router.get("")
def get_recommendations(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Recommendations are for customers only")

    user_id = current_user["user_id"]
    with get_db() as cur:
        cur.execute("SELECT * FROM get_user_recommendations(%s)", (user_id,))
        rows = cur.fetchall()

    return [
        {
            "movie_id": r["movieid"],
            "title": r["title"],
            "genre": r["genre"],
            "tmdb_rating": float(r["tmdb_rating"]) if r["tmdb_rating"] else None,
            "tmdb_popularity": float(r["tmdb_popularity"]) if r["tmdb_popularity"] else None,
            "trending_status": r["trendingstatus"],
            "next_showtime": r["nextshowtime"].isoformat() if r["nextshowtime"] else None,
            "base_price": float(r["baseprice"]) if r["baseprice"] else None,
            "recommendation_score": float(r["recommendationscore"]) if r["recommendationscore"] else 0,
            "rank": r["rank"],
        }
        for r in rows
    ]
