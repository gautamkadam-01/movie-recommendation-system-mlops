"""
tmdb_service.py
Robust TMDB API integration with multi-tier caching, timeout protection,
and aesthetic Netflix-themed fallback image generation.
"""

import requests
import urllib.parse
from database import get_tmdb_cache, set_tmdb_cache

TMDB_API_KEY = "8265bd1679663a7ea12ac168da84d2e8"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
POSTER_SIZE = "w500"
BACKDROP_SIZE = "w1280"

# In-memory LRU-style cache
_MEMORY_CACHE = {}

def generate_svg_poster(title: str, year: str = "", genre: str = "Movie") -> str:
    """Generates an aesthetic inline SVG poster if TMDB poster is unavailable."""
    safe_title = (title[:22] + "...") if len(title) > 25 else title
    safe_genre = genre.upper() if genre else "FEATURE"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" viewBox="0 0 300 450">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#1f1f1f"/>
          <stop offset="50%" stop-color="#141414"/>
          <stop offset="100%" stop-color="#0a0a0a"/>
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="30%" r="50%">
          <stop offset="0%" stop-color="#e50914" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#141414" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="300" height="450" fill="url(#g)"/>
      <circle cx="150" cy="140" r="120" fill="url(#glow)"/>
      <text x="150" y="70" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="28" font-weight="900" fill="#E50914" text-anchor="middle" letter-spacing="4">NETFLIX</text>
      <rect x="30" y="100" width="240" height="2" fill="#E50914" opacity="0.4"/>
      <circle cx="150" cy="200" r="45" fill="#222" stroke="#E50914" stroke-width="2"/>
      <polygon points="144,185 162,200 144,215" fill="#FFF"/>
      <text x="150" y="310" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="18" font-weight="700" fill="#FFF" text-anchor="middle">{safe_title}</text>
      <text x="150" y="340" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="12" font-weight="600" fill="#E50914" text-anchor="middle" letter-spacing="2">{safe_genre}</text>
      <text x="150" y="365" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="12" fill="#888" text-anchor="middle">{year}</text>
      <rect x="20" y="20" width="260" height="410" fill="none" stroke="#333" stroke-width="1" rx="8"/>
    </svg>"""
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)

def generate_svg_backdrop(title: str) -> str:
    """Generates an aesthetic inline SVG backdrop banner."""
    safe_title = (title[:35] + "...") if len(title) > 38 else title
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#2a0808"/>
          <stop offset="60%" stop-color="#141414"/>
          <stop offset="100%" stop-color="#050505"/>
        </linearGradient>
      </defs>
      <rect width="1280" height="720" fill="url(#bg)"/>
      <text x="640" y="340" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="48" font-weight="800" fill="#FFFFFF" text-anchor="middle">{safe_title}</text>
      <text x="640" y="400" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="20" font-weight="600" fill="#E50914" text-anchor="middle" letter-spacing="4">NOW STREAMING</text>
    </svg>"""
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)

def fetch_tmdb_details(movie_id: int):
    """Fetches posters, backdrop, and trailer video key from TMDB."""
    if movie_id in _MEMORY_CACHE:
        return _MEMORY_CACHE[movie_id]

    # Check SQLite cache
    cached = get_tmdb_cache(movie_id)
    if cached and cached.get("poster_path") and cached.get("backdrop_path"):
        res = {
            "poster_path": cached.get("poster_path"),
            "backdrop_path": cached.get("backdrop_path"),
            "trailer_key": cached.get("trailer_key")
        }
        _MEMORY_CACHE[movie_id] = res
        return res

    poster_path = None
    backdrop_path = None
    trailer_key = None

    try:
        # 1. Fetch movie details
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            poster_path = data.get("poster_path")
            backdrop_path = data.get("backdrop_path")
    except Exception:
        pass

    try:
        # 2. Fetch trailer video
        vid_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
        vid_resp = requests.get(vid_url, timeout=3)
        if vid_resp.status_code == 200:
            v_data = vid_resp.json().get("results", [])
            for v in v_data:
                if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser", "Clip"]:
                    trailer_key = v.get("key")
                    break
    except Exception:
        pass

    # Save to SQLite cache
    set_tmdb_cache(movie_id, poster_path, backdrop_path, trailer_key)
    res = {
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "trailer_key": trailer_key
    }
    _MEMORY_CACHE[movie_id] = res
    return res

def get_image_urls(movie_dict: dict, fetch_remote: bool = False):
    """Returns URLs for poster and backdrop with instant fallback."""
    mid = movie_dict.get("movie_id")
    title = movie_dict.get("title", "Movie")
    year = movie_dict.get("year", "")
    genre = movie_dict.get("genres", ["Movie"])[0] if movie_dict.get("genres") else "Movie"

    poster_path = movie_dict.get("poster_path")
    backdrop_path = movie_dict.get("backdrop_path")

    # If missing and fetch_remote is requested, check memory/SQLite or fetch
    if (not poster_path or not backdrop_path) and fetch_remote and mid:
        details = fetch_tmdb_details(mid)
        if not poster_path:
            poster_path = details.get("poster_path")
        if not backdrop_path:
            backdrop_path = details.get("backdrop_path")
        if not movie_dict.get("trailer_key"):
            movie_dict["trailer_key"] = details.get("trailer_key")

    poster_url = f"{TMDB_IMAGE_BASE}/{POSTER_SIZE}{poster_path}" if poster_path else generate_svg_poster(title, year, genre)
    backdrop_url = f"{TMDB_IMAGE_BASE}/{BACKDROP_SIZE}{backdrop_path}" if backdrop_path else generate_svg_backdrop(title)

    return {
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "trailer_key": movie_dict.get("trailer_key")
    }
