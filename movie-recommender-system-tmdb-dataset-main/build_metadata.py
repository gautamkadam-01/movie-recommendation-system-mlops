"""
build_metadata.py
Precomputes clean, fast JSON metadata cache for all 4806 movies from TMDB dataset.
Combines movie_list.pkl with tmdb_5000_movies.csv and tmdb_5000_credits.csv.
"""

import pickle
import pandas as pd
import json
import ast
import os
import requests
import concurrent.futures

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
CACHE_FILE = os.path.join(MODEL_DIR, "movies_cache.json")

DOWNLOADS_DIR = r"C:\Users\hp\Downloads"
MOVIES_CSV = os.path.join(DOWNLOADS_DIR, "tmdb_5000_movies.csv", "tmdb_5000_movies.csv")
CREDITS_CSV = os.path.join(DOWNLOADS_DIR, "tmdb_5000_credits", "tmdb_5000_credits.csv")
MOVIE_LIST_PKL = os.path.join(MODEL_DIR, "movie_list.pkl")

TMDB_API_KEY = "8265bd1679663a7ea12ac168da84d2e8"

def parse_json(val, key=None):
    if not isinstance(val, str) or not val.strip():
        return []
    try:
        items = ast.literal_eval(val)
        if key:
            return [item.get(key) for item in items if isinstance(item, dict) and key in item]
        return items
    except:
        return []

def get_director(crew_val):
    items = parse_json(crew_val)
    for c in items:
        if c.get("job") == "Director":
            return c.get("name", "")
    return ""

def format_runtime(minutes):
    if not minutes or pd.isna(minutes) or minutes <= 0:
        return "1h 50m"
    m = int(minutes)
    hours = m // 60
    mins = m % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

def fetch_tmdb_images(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return {
                "movie_id": movie_id,
                "poster_path": data.get("poster_path"),
                "backdrop_path": data.get("backdrop_path")
            }
    except:
        pass
    return {"movie_id": movie_id, "poster_path": None, "backdrop_path": None}

def build():
    print("[1/4] Loading dataset files...")
    movie_list = pickle.load(open(MOVIE_LIST_PKL, "rb"))
    movie_list["matrix_index"] = movie_list.index

    movies_csv = pd.read_csv(MOVIES_CSV)
    credits_csv = pd.read_csv(CREDITS_CSV)

    print("[2/4] Parsing genres, keywords, cast, and crew...")
    movies_merged = movies_csv.merge(credits_csv, on="title")
    movies_merged["genres_list"] = movies_merged["genres"].apply(lambda x: parse_json(x, "name"))
    movies_merged["keywords_list"] = movies_merged["keywords"].apply(lambda x: parse_json(x, "name"))
    movies_merged["cast_list"] = movies_merged["cast"].apply(lambda x: parse_json(x, "name")[:5])
    movies_merged["director"] = movies_merged["crew"].apply(get_director)

    # De-duplicate movies_merged by id
    movies_merged = movies_merged.drop_duplicates(subset=["id"])

    # Merge with movie_list to preserve matrix_index order
    merged = movie_list[["movie_id", "matrix_index", "title"]].merge(
        movies_merged[[
            "id", "overview", "genres_list", "keywords_list", "cast_list", "director",
            "release_date", "vote_average", "vote_count", "popularity", "runtime", "tagline"
        ]],
        left_on="movie_id", right_on="id", how="left"
    )

    print("[3/4] Preparing movie records...")
    movies = []
    top_movie_ids = []

    for _, row in merged.iterrows():
        mid = int(row["movie_id"])
        matrix_idx = int(row["matrix_index"])
        title = str(row["title"])
        overview = str(row["overview"]) if pd.notna(row["overview"]) else "No overview available."
        genres = row["genres_list"] if isinstance(row["genres_list"], list) else ["Drama"]
        keywords = row["keywords_list"] if isinstance(row["keywords_list"], list) else []
        cast = row["cast_list"] if isinstance(row["cast_list"], list) else []
        director = str(row["director"]) if pd.notna(row["director"]) else "Unknown"
        rel_date = str(row["release_date"]) if pd.notna(row["release_date"]) else "2015-01-01"
        year = rel_date.split("-")[0] if "-" in rel_date else "2015"
        vote_avg = round(float(row["vote_average"]), 1) if pd.notna(row["vote_average"]) else 7.0
        vote_count = int(row["vote_count"]) if pd.notna(row["vote_count"]) else 100
        popularity = round(float(row["popularity"]), 2) if pd.notna(row["popularity"]) else 10.0
        runtime_min = float(row["runtime"]) if pd.notna(row["runtime"]) else 110.0
        runtime_str = format_runtime(runtime_min)
        tagline = str(row["tagline"]) if pd.notna(row["tagline"]) and str(row["tagline"]) != "nan" else ""

        # Compute a Netflix match percentage (e.g. 85% - 99%)
        match_pct = min(99, max(75, int(vote_avg * 10 + min(vote_count / 1000, 15))))

        m = {
            "movie_id": mid,
            "matrix_index": matrix_idx,
            "title": title,
            "overview": overview,
            "genres": genres,
            "keywords": keywords,
            "cast": cast,
            "director": director,
            "release_date": rel_date,
            "year": year,
            "vote_average": vote_avg,
            "vote_count": vote_count,
            "popularity": popularity,
            "runtime": runtime_str,
            "tagline": tagline,
            "match_pct": match_pct,
            "poster_path": None,
            "backdrop_path": None
        }
        movies.append(m)

    # Sort by popularity to pick top ~100 movies for pre-cached TMDB posters
    sorted_by_pop = sorted(movies, key=lambda x: x["popularity"], reverse=True)
    top_movie_ids = [m["movie_id"] for m in sorted_by_pop[:120]]

    print(f"[4/4] Pre-fetching TMDB posters & backdrops for top {len(top_movie_ids)} trending movies...")
    img_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_tmdb_images, top_movie_ids)
        for r in results:
            img_map[r["movie_id"]] = (r["poster_path"], r["backdrop_path"])

    for m in movies:
        if m["movie_id"] in img_map:
            m["poster_path"], m["backdrop_path"] = img_map[m["movie_id"]]

    print(f"Saving {len(movies)} movies to {CACHE_FILE}...")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False)

    print("Metadata cache successfully built!")

if __name__ == "__main__":
    build()
