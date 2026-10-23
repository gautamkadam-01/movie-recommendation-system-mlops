"""
main.py
Production-ready FastAPI backend for Netflix-style Movie Recommendation Application.
Handles API routing, static frontend mounting, recommendation pipelines,
state management (Watch/Search History & Watchlist), and error resilience.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import database
from engine import engine
import tmdb_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ML models and metadata
    database.init_db()
    engine.load()
    yield
    # Shutdown logic if any

app = FastAPI(
    title="Netflix Movie Recommender API",
    description="Full-stack Netflix-style Content-Based Movie Recommendation Engine",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class SelectProfileRequest(BaseModel):
    profile_id: int

class WatchProgressRequest(BaseModel):
    movie_id: int
    progress_pct: Optional[int] = 25
    duration_watched: Optional[str] = "35m"

class WatchlistToggleRequest(BaseModel):
    movie_id: int

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Netflix Movie Recommender API is running. Static UI not found."}

# ================= PROFILES API =================
@app.get("/api/profiles")
async def get_profiles():
    return database.get_profiles()

@app.get("/api/profiles/active")
async def get_active_profile():
    return database.get_active_profile()

@app.post("/api/profiles/select")
async def select_profile(req: SelectProfileRequest):
    profile = database.set_active_profile(req.profile_id)
    return {"status": "success", "profile": profile}

# ================= MOVIES & CAROUSELS API =================
@app.get("/api/movies/hero")
async def get_hero():
    active_profile = database.get_active_profile()
    hero = engine.get_hero_movie(active_profile["id"])
    if not hero:
        raise HTTPException(status_code=404, detail="Hero movie unavailable")
    
    # Check watchlist status
    in_watchlist = database.is_in_watchlist(active_profile["id"], hero["movie_id"])
    hero_resp = dict(hero)
    hero_resp["in_watchlist"] = in_watchlist
    return hero_resp

@app.get("/api/movies/carousels")
async def get_carousels():
    active_profile = database.get_active_profile()
    rows = engine.get_carousel_rows(active_profile["id"])
    
    # Annotate watchlist status for each movie in carousels
    watchlist = database.get_watchlist(active_profile["id"])
    watchlist_ids = {w["movie_id"] for w in watchlist}
    for row in rows:
        for m in row.get("movies", []):
            if m:
                m["in_watchlist"] = m["movie_id"] in watchlist_ids
                
    return rows

# Search endpoint placed BEFORE {movie_id} to avoid path parameter shadowing
@app.get("/api/movies/search")
async def search_movies(q: str = Query(..., min_length=1), limit: int = 24):
    active_profile = database.get_active_profile()
    results = engine.search_movies(q, profile_id=active_profile["id"], limit=limit)
    
    # Annotate watchlist
    watchlist_ids = {w["movie_id"] for w in database.get_watchlist(active_profile["id"])}
    for r in results:
        r["in_watchlist"] = r["movie_id"] in watchlist_ids

    return {
        "query": q,
        "count": len(results),
        "results": results
    }

@app.get("/api/movies/{movie_id}")
async def get_movie_detail(movie_id: int):
    movie = engine.get_movie_by_id(movie_id, fetch_remote=True)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    active_profile = database.get_active_profile()
    in_watchlist = database.is_in_watchlist(active_profile["id"], movie_id)

    # 5-6 similar recommended movies
    similar = engine.get_similar_movies(movie_id, top_n=6)
    watchlist = database.get_watchlist(active_profile["id"])
    watchlist_ids = {w["movie_id"] for w in watchlist}
    for sim in similar:
        sim["in_watchlist"] = sim["movie_id"] in watchlist_ids

    # Video trailer
    tmdb_info = tmdb_service.fetch_tmdb_details(movie_id)
    trailer_key = tmdb_info.get("trailer_key")

    resp = dict(movie)
    resp["in_watchlist"] = in_watchlist
    resp["trailer_key"] = trailer_key
    resp["similar_recommendations"] = similar
    return resp

# ================= WATCH HISTORY API =================
@app.get("/api/history/watch")
async def get_watch_history():
    active_profile = database.get_active_profile()
    history = database.get_watch_history(active_profile["id"])
    # Enrich with movie details
    enriched = []
    for h in history:
        m = engine.get_movie_by_id(h["movie_id"])
        if m:
            item = dict(m)
            item["progress_pct"] = h["progress_pct"]
            item["duration_watched"] = h["duration_watched"]
            item["last_watched_at"] = h["last_watched_at"]
            enriched.append(item)
    return enriched

@app.post("/api/history/watch")
async def record_watch(req: WatchProgressRequest):
    active_profile = database.get_active_profile()
    movie = engine.get_movie_by_id(req.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    database.record_watch(
        profile_id=active_profile["id"],
        movie_id=req.movie_id,
        movie_title=movie["title"],
        poster_path=movie.get("poster_url"),
        progress_pct=req.progress_pct or 30,
        duration_watched=req.duration_watched or "40m"
    )
    return {"status": "success", "message": f"Watched '{movie['title']}' recorded"}

@app.delete("/api/history/watch/{movie_id}")
async def delete_watch_item(movie_id: int):
    active_profile = database.get_active_profile()
    database.delete_watch_history_item(active_profile["id"], movie_id)
    return {"status": "success", "message": "History item removed"}

@app.delete("/api/history/watch")
async def clear_watch_history():
    active_profile = database.get_active_profile()
    database.clear_watch_history(active_profile["id"])
    return {"status": "success", "message": "Watch history cleared"}

# ================= SEARCH HISTORY API =================
@app.get("/api/history/search")
async def get_search_history():
    active_profile = database.get_active_profile()
    return database.get_search_history(active_profile["id"])

@app.delete("/api/history/search/{query_id}")
async def delete_search_item(query_id: int):
    active_profile = database.get_active_profile()
    database.delete_search_history_item(active_profile["id"], query_id)
    return {"status": "success", "message": "Search query removed"}

@app.delete("/api/history/search")
async def clear_search_history():
    active_profile = database.get_active_profile()
    database.clear_search_history(active_profile["id"])
    return {"status": "success", "message": "Search history cleared"}

# ================= WATCHLIST API =================
@app.get("/api/watchlist")
async def get_watchlist():
    active_profile = database.get_active_profile()
    items = database.get_watchlist(active_profile["id"])
    enriched = []
    for item in items:
        m = engine.get_movie_by_id(item["movie_id"])
        if m:
            m_copy = dict(m)
            m_copy["in_watchlist"] = True
            m_copy["added_at"] = item["added_at"]
            enriched.append(m_copy)
    return enriched

@app.post("/api/watchlist/toggle")
async def toggle_watchlist(req: WatchlistToggleRequest):
    active_profile = database.get_active_profile()
    movie = engine.get_movie_by_id(req.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    is_saved = database.toggle_watchlist(
        profile_id=active_profile["id"],
        movie_id=req.movie_id,
        movie_title=movie["title"],
        poster_path=movie.get("poster_url")
    )
    return {
        "status": "success",
        "movie_id": req.movie_id,
        "is_saved": is_saved,
        "message": "Added to Watchlist" if is_saved else "Removed from Watchlist"
    }

# ================= PERSONALIZED RECOMMENDATIONS API =================
@app.get("/api/recommendations/personalized")
async def get_personalized_recommendations():
    active_profile = database.get_active_profile()
    recs = engine.get_personalized_recommendations(active_profile["id"], top_n=18)
    watchlist_ids = {w["movie_id"] for w in database.get_watchlist(active_profile["id"])}
    for r in recs:
        r["in_watchlist"] = r["movie_id"] in watchlist_ids
    return recs

# ================= SYSTEM HEALTH API =================
@app.get("/api/status")
async def system_status():
    return {
        "status": "online",
        "total_movies": len(engine.movies),
        "similarity_loaded": engine.similarity is not None,
        "active_profile": database.get_active_profile(),
        "total_profiles": len(database.get_profiles())
    }

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  NETFLIX MOVIE RECOMMENDER SYSTEM")
    print("  FastAPI Server running at: http://127.0.0.1:8000")
    print("="*60 + "\n")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
