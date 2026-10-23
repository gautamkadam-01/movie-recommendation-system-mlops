"""
engine.py
Recommendation engine and content-based filtering pipeline.
Loads similarity matrix, movie lists, and cached TMDB metadata.
Provides vector-blended personalized recommendations based on Watch History and Search History.
"""

import os
import json
import pickle
import numpy as np
from typing import List, Dict, Any, Optional
import database
import tmdb_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Model file paths with multi-directory discovery
CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "model"),
    BASE_DIR,
    r"c:\Users\hp\Downloads",
    r"c:\Users\hp\Downloads\movie-recommender-system-tmdb-dataset-main"
]

def find_file(filename: str) -> Optional[str]:
    for p in CANDIDATE_PATHS:
        full_path = os.path.join(p, filename)
        if os.path.exists(full_path):
            return full_path
    return None

class MovieRecommenderEngine:
    def __init__(self):
        self.movies: List[Dict[str, Any]] = []
        self.movie_id_map: Dict[int, Dict[str, Any]] = {}
        self.matrix_idx_map: Dict[int, Dict[str, Any]] = {}
        self.similarity: Optional[np.ndarray] = None
        self.loaded = False

    def load(self):
        if self.loaded:
            return

        print("[Engine] Initializing recommendation engine...")
        
        # 1. Load precomputed metadata cache
        cache_path = find_file("movies_cache.json")
        if cache_path and os.path.exists(cache_path):
            print(f"[Engine] Loading metadata cache from {cache_path}...")
            with open(cache_path, "r", encoding="utf-8") as f:
                self.movies = json.load(f)
        else:
            print("[Engine] movies_cache.json not found, loading movie_list.pkl...")
            pkl_path = find_file("movie_list.pkl")
            if not pkl_path:
                raise FileNotFoundError("Could not find movie_list.pkl in any search directory!")
            with open(pkl_path, "rb") as f:
                df = pickle.load(f)
                self.movies = []
                for idx, row in df.iterrows():
                    self.movies.append({
                        "movie_id": int(row["movie_id"]),
                        "matrix_index": int(idx),
                        "title": str(row["title"]),
                        "overview": "Overview unavailable.",
                        "genres": ["Movie"],
                        "keywords": [],
                        "cast": [],
                        "director": "Unknown",
                        "year": "2015",
                        "vote_average": 7.0,
                        "vote_count": 500,
                        "popularity": 20.0,
                        "runtime": "1h 45m",
                        "tagline": "",
                        "match_pct": 88,
                        "poster_path": None,
                        "backdrop_path": None
                    })

        # Build fast lookup indexes
        for m in self.movies:
            mid = m["movie_id"]
            matrix_idx = m["matrix_index"]
            self.movie_id_map[mid] = m
            self.matrix_idx_map[matrix_idx] = m

        # 2. Load similarity matrix
        sim_path = find_file("similarity.pkl")
        if sim_path and os.path.exists(sim_path):
            print(f"[Engine] Loading similarity matrix from {sim_path}...")
            with open(sim_path, "rb") as f:
                self.similarity = pickle.load(f)
            print(f"[Engine] Similarity matrix loaded successfully. Shape: {self.similarity.shape}")
        else:
            print("[Engine] WARNING: similarity.pkl not found! Similarity recommendations will fall back to genre similarity.")
            self.similarity = None

        self.loaded = True
        print(f"[Engine] Loaded {len(self.movies)} movies successfully.")

    def get_movie_by_id(self, movie_id: int, fetch_remote: bool = False) -> Optional[Dict[str, Any]]:
        m = self.movie_id_map.get(movie_id)
        if not m:
            return None
        enriched = dict(m)
        urls = tmdb_service.get_image_urls(enriched, fetch_remote=fetch_remote)
        enriched.update(urls)
        return enriched

    def get_movie_by_matrix_idx(self, matrix_idx: int, fetch_remote: bool = False) -> Optional[Dict[str, Any]]:
        m = self.matrix_idx_map.get(matrix_idx)
        if not m:
            return None
        enriched = dict(m)
        urls = tmdb_service.get_image_urls(enriched, fetch_remote=fetch_remote)
        enriched.update(urls)
        return enriched

    def get_similar_movies(self, movie_id: int, top_n: int = 5) -> List[Dict[str, Any]]:
        """Returns top_n similar movies using cosine similarity matrix."""
        movie = self.movie_id_map.get(movie_id)
        if not movie:
            return []

        matrix_idx = movie.get("matrix_index")
        if self.similarity is not None and matrix_idx is not None and matrix_idx < len(self.similarity):
            sim_scores = self.similarity[matrix_idx]
            # argsort descending
            top_indices = np.argsort(sim_scores)[::-1]
            results = []
            for idx in top_indices:
                if int(idx) == matrix_idx:
                    continue
                cand = self.get_movie_by_matrix_idx(int(idx))
                if cand:
                    cand_copy = dict(cand)
                    cand_copy["similarity_score"] = float(sim_scores[idx])
                    cand_copy["match_pct"] = min(99, max(70, int(sim_scores[idx] * 100)))
                    results.append(cand_copy)
                if len(results) >= top_n:
                    break
            return results

        # Fallback if similarity matrix is unavailable
        genres_target = set(movie.get("genres", []))
        cands = [
            m for m in self.movies 
            if m["movie_id"] != movie_id and len(genres_target.intersection(set(m.get("genres", [])))) > 0
        ]
        cands = sorted(cands, key=lambda x: x.get("popularity", 0), reverse=True)[:top_n]
        return [self.get_movie_by_id(c["movie_id"]) for c in cands]

    def get_personalized_recommendations(self, profile_id: int, top_n: int = 12) -> List[Dict[str, Any]]:
        """
        Dynamically calculates personalized recommendations by:
        1. Averaging similarity vectors of recently watched movies (with recency decay).
        2. Boosting similarity with recent search keywords and genres.
        3. Blending with popularity prior.
        """
        watch_history = database.get_watch_history(profile_id, limit=10)
        search_history = database.get_search_history(profile_id, limit=6)

        watched_ids = {item["movie_id"] for item in watch_history}

        # Case 1: No watch history -> return top rated/popular picks
        if not watch_history or self.similarity is None:
            sorted_movies = sorted(
                [m for m in self.movies if m["movie_id"] not in watched_ids],
                key=lambda x: (x.get("vote_average", 0) * 2 + np.log1p(x.get("popularity", 0))),
                reverse=True
            )[:top_n]
            return [self.get_movie_by_id(m["movie_id"]) for m in sorted_movies]

        # Case 2: User has watch history -> compute weighted average vector
        n_movies = len(self.similarity)
        user_vector = np.zeros(n_movies, dtype=np.float32)
        total_weight = 0.0

        for i, item in enumerate(watch_history):
            mid = item["movie_id"]
            m_obj = self.movie_id_map.get(mid)
            if m_obj and m_obj.get("matrix_index") is not None:
                m_idx = m_obj["matrix_index"]
                if m_idx < n_movies:
                    # Exponential recency decay: 0.85^i
                    weight = 0.85 ** i
                    # Give extra weight if watched further
                    progress = item.get("progress_pct", 25)
                    progress_mult = 1.0 + (progress / 100.0) * 0.5
                    w = weight * progress_mult
                    user_vector += w * self.similarity[m_idx]
                    total_weight += w

        if total_weight > 0:
            user_vector /= total_weight

        # Boost from recent search history
        if search_history:
            search_terms = [sh["query"].lower() for sh in search_history]
            boost_vector = np.zeros(n_movies, dtype=np.float32)
            
            for m in self.movies:
                idx = m.get("matrix_index")
                if idx is not None and idx < n_movies:
                    title_l = m["title"].lower()
                    genres_l = [g.lower() for g in m.get("genres", [])]
                    cast_l = [c.lower() for c in m.get("cast", [])]
                    dir_l = m.get("director", "").lower()
                    kw_l = [k.lower() for k in m.get("keywords", [])]

                    score = 0.0
                    for q in search_terms:
                        if q in title_l:
                            score += 0.4
                        if any(q in g for g in genres_l):
                            score += 0.3
                        if any(q in c for c in cast_l):
                            score += 0.35
                        if q in dir_l:
                            score += 0.35
                        if any(q in k for k in kw_l):
                            score += 0.2
                    if score > 0:
                        boost_vector[idx] = min(score, 1.0)
            
            # Blend user vector with search boost
            user_vector = 0.75 * user_vector + 0.25 * boost_vector

        # Add small popularity prior so quality movies surface
        pop_scores = np.array([min(m.get("popularity", 0) / 100.0, 1.0) for m in self.movies], dtype=np.float32)
        final_scores = 0.85 * user_vector + 0.15 * pop_scores

        top_indices = np.argsort(final_scores)[::-1]
        results = []
        for idx in top_indices:
            idx_int = int(idx)
            cand = self.matrix_idx_map.get(idx_int)
            if cand and cand["movie_id"] not in watched_ids:
                enriched = self.get_movie_by_id(cand["movie_id"])
                if enriched:
                    enriched["match_pct"] = min(99, max(78, int(final_scores[idx_int] * 90 + 10)))
                    results.append(enriched)
            if len(results) >= top_n:
                break

        return results

    def get_because_you_watched(self, profile_id: int, top_n: int = 10) -> Optional[Dict[str, Any]]:
        """Returns recommendations based on the most recently watched movie."""
        history = database.get_watch_history(profile_id, limit=1)
        if not history:
            return None

        last_watched = history[0]
        mid = last_watched["movie_id"]
        source_movie = self.get_movie_by_id(mid)
        if not source_movie:
            return None

        watched_ids = {item["movie_id"] for item in database.get_watch_history(profile_id, limit=20)}
        sim_movies = self.get_similar_movies(mid, top_n=top_n + len(watched_ids))
        filtered = [m for m in sim_movies if m["movie_id"] not in watched_ids][:top_n]

        return {
            "source_movie": source_movie,
            "recommendations": filtered
        }

    def get_continue_watching(self, profile_id: int) -> List[Dict[str, Any]]:
        history = database.get_watch_history(profile_id, limit=10)
        items = []
        for h in history:
            m = self.get_movie_by_id(h["movie_id"])
            if m:
                m_copy = dict(m)
                m_copy["progress_pct"] = h["progress_pct"]
                m_copy["duration_watched"] = h["duration_watched"]
                m_copy["last_watched_at"] = h["last_watched_at"]
                items.append(m_copy)
        return items

    def search_movies(self, query: str, profile_id: Optional[int] = None, limit: int = 24) -> List[Dict[str, Any]]:
        """
        Multi-attribute instant search matching:
        - Movie Title
        - Director
        - Cast members
        - Genres
        - Keywords
        """
        q = query.strip().lower()
        if not q:
            return []

        scored = []
        for m in self.movies:
            score = 0.0
            title_l = m["title"].lower()
            dir_l = m.get("director", "").lower()
            cast_l = [c.lower() for c in m.get("cast", [])]
            genres_l = [g.lower() for g in m.get("genres", [])]
            keywords_l = [k.lower() for k in m.get("keywords", [])]

            # Exact title match
            if title_l == q:
                score += 100.0
            elif title_l.startswith(q):
                score += 50.0
            elif q in title_l:
                score += 30.0

            # Director match
            if q in dir_l:
                score += 40.0

            # Cast match
            for c in cast_l:
                if q in c:
                    score += 35.0
                    break

            # Genre match
            for g in genres_l:
                if q in g or g in q:
                    score += 25.0
                    break

            # Keywords match
            for k in keywords_l:
                if q in k:
                    score += 15.0
                    break

            if score > 0:
                # Add popularity tie-breaker
                score += min(m.get("popularity", 0) / 10.0, 10.0)
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [self.get_movie_by_id(m["movie_id"]) for _, m in scored[:limit]]

        # Record in search history
        if profile_id:
            database.record_search(profile_id, query, len(results))

        return results

    def get_hero_movie(self, profile_id: int = 1) -> Dict[str, Any]:
        """Selects a premium high-res movie for the Netflix hero banner."""
        # Blockbusters with proven high-res backdrops and trailers
        hero_candidates = [
            19995,  # Avatar
            157336, # Interstellar
            27205,  # Inception
            49026,  # The Dark Knight Rises
            299536, # Avengers: Infinity War / 24428 Avengers
            680,    # Pulp Fiction
            550,    # Fight Club
            155,    # The Dark Knight
            24428,  # The Avengers
        ]
        for mid in hero_candidates:
            m = self.get_movie_by_id(mid)
            if m and m.get("backdrop_url") and not m.get("backdrop_url").startswith("data:image/svg"):
                return m

        # Fallback to top popular
        top_popular = sorted(self.movies, key=lambda x: x.get("popularity", 0), reverse=True)[0]
        return self.get_movie_by_id(top_popular["movie_id"])

    def get_carousel_rows(self, profile_id: int) -> List[Dict[str, Any]]:
        """Builds all homepage carousel rows."""
        rows = []

        # 1. Continue Watching (if items exist)
        continue_watching = self.get_continue_watching(profile_id)
        if continue_watching:
            rows.append({
                "id": "continue_watching",
                "title": "Continue Watching",
                "type": "continue_watching",
                "movies": continue_watching
            })

        # 2. Top Picks for You (Personalized Recommendations)
        top_picks = self.get_personalized_recommendations(profile_id, top_n=12)
        if top_picks:
            rows.append({
                "id": "top_picks",
                "title": "Top Picks for You",
                "subtitle": "Personalized based on your viewing & search taste",
                "type": "personalized",
                "movies": top_picks
            })

        # 3. Because You Watched [Movie]
        because_watched = self.get_because_you_watched(profile_id, top_n=10)
        if because_watched and because_watched["recommendations"]:
            src = because_watched["source_movie"]
            rows.append({
                "id": f"because_{src['movie_id']}",
                "title": f"Because You Watched {src['title']}",
                "subtitle": f"Similar to {src['title']}",
                "type": "content_based",
                "movies": because_watched["recommendations"]
            })

        # 4. Trending Now (sorted by popularity)
        trending = sorted(self.movies, key=lambda x: x.get("popularity", 0), reverse=True)[:14]
        rows.append({
            "id": "trending_now",
            "title": "Trending Now",
            "type": "standard",
            "movies": [self.get_movie_by_id(m["movie_id"]) for m in trending]
        })

        # 5. Sci-Fi Hits
        scifi = [
            m for m in self.movies 
            if any("Science Fiction" in g or "Fantasy" in g for g in m.get("genres", []))
        ]
        scifi_sorted = sorted(scifi, key=lambda x: x.get("popularity", 0), reverse=True)[:14]
        rows.append({
            "id": "scifi_hits",
            "title": "Sci-Fi & Cyberpunk Hits",
            "type": "standard",
            "movies": [self.get_movie_by_id(m["movie_id"]) for m in scifi_sorted]
        })

        # 6. Action & Adrenaline
        action = [
            m for m in self.movies 
            if any("Action" in g or "Adventure" in g for g in m.get("genres", []))
        ]
        action_sorted = sorted(action, key=lambda x: x.get("popularity", 0), reverse=True)[:14]
        rows.append({
            "id": "action_adventure",
            "title": "Action & High Adrenaline",
            "type": "standard",
            "movies": [self.get_movie_by_id(m["movie_id"]) for m in action_sorted]
        })

        # 7. Critically Acclaimed Masterpieces
        critics = [
            m for m in self.movies 
            if m.get("vote_average", 0) >= 7.6 and m.get("vote_count", 0) >= 2000
        ]
        critics_sorted = sorted(critics, key=lambda x: x.get("vote_average", 0), reverse=True)[:14]
        rows.append({
            "id": "critics_acclaimed",
            "title": "Critically Acclaimed Masterpieces",
            "type": "standard",
            "movies": [self.get_movie_by_id(m["movie_id"]) for m in critics_sorted]
        })

        # 8. Mind-Bending Thrillers & Mysteries
        thrillers = [
            m for m in self.movies 
            if any("Thriller" in g or "Mystery" in g or "Crime" in g for g in m.get("genres", []))
        ]
        thrillers_sorted = sorted(thrillers, key=lambda x: x.get("popularity", 0), reverse=True)[:14]
        rows.append({
            "id": "thrillers",
            "title": "Mind-Bending Thrillers & Mysteries",
            "type": "standard",
            "movies": [self.get_movie_by_id(m["movie_id"]) for m in thrillers_sorted]
        })

        return rows

# Singleton engine instance
engine = MovieRecommenderEngine()
