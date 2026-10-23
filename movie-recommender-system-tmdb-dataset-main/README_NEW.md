# 🎬 Netflix-Style Movie Recommender System (Production Edition)

A production-ready, full-stack, Netflix-aesthetic movie streaming and recommendation web application powered by **FastAPI**, **Scikit-Learn**, **SQLite**, and **Vanilla Modern JavaScript/CSS3**.

Transformed from a basic Streamlit prototype into an ultra-fast, responsive platform with deep personalization, watch history progress tracking, intelligent multi-attribute search, and interactive video trailers.

---

## 🌟 Key Features

### 1. 🍿 Authentic Netflix UI/UX Design
- **Signature Netflix Aesthetic**: Deep `#141414` dark background, `#E50914` crimson red accents, crisp white typography, and glassmorphism navbar.
- **Cinematic Hero Banner**: Large featured blockbuster backdrop, metadata badges (`98% Match`, release year, runtime, `Ultra HD 4K`, vote stars), overview synopsis, and quick actions (`Play Trailer`, `More Info`, `+ Watchlist`).
- **Smooth Horizontal Carousels**: Left and right carousel sliders with smooth scrolling and responsive card zoom (`scale(1.08)` hover effects, quick-play button, watchlist toggle, and metadata preview).
- **Interactive Movie Detail Modal**: Rich pop-up displaying backdrop, trailer video player, director, top cast, genre chips, tagline, and **5-6 similar content-based recommendations** with 1-click modal navigation.
- **Interactive Video Trailer Player**: Plays authentic movie trailers via embedded YouTube player with automatic playback progress logging.

### 2. 🧠 Dynamic Vector-Blended Personalization Engine
- **Content-Based Filtering**: Leverages the 4,806 × 4,806 Cosine Similarity matrix (`similarity.pkl`) computed over genres, keywords, cast, crew, and overviews.
- **Watch History Vector Blending**: Computes a weighted average of similarity vectors across recently watched movies using exponential recency decay ($\lambda = 0.85^i$) and playback progress weights:
  $$V_{watch} = \sum_{i=1}^{K} w_i \cdot S[idx_i]$$
- **Search Intent Boosting**: Analyzes recent search queries for actors, directors, genres, and keywords to inject an additive interest boost into the recommendation vector:
  $$V_{final} = 0.75 \cdot V_{watch} + 0.25 \cdot V_{search}$$
- **Dynamic "Because You Watched [Title]" Row**: Adapts in real-time to the user's latest watched title.

### 3. 🔍 Intelligent Multi-Attribute Search & Search History
- **Instant Debounced Auto-complete**: Global search bar in navbar with 280ms debounced auto-complete dropdown showing instant poster previews and metadata.
- **Multi-Attribute Search Matching**: Queries match not just titles, but also **actors**, **directors**, **genres**, and **plot keywords** (e.g. searching *"Nolan"* finds all Christopher Nolan films; searching *"DiCaprio"* finds Leonardo DiCaprio films).
- **Persistent Search History**: Every query is logged with timestamp and match count in SQLite. Users can view past searches, re-query in 1 click, or clear their search history.

### 4. 🕒 Watch History & Continue Watching Row
- **Automatic Playback Progress Tracking**: Clicking "Play" logs the movie into the active profile's watch history with progress percentage (e.g., 45% completed) and duration.
- **Dedicated "Continue Watching" Carousel**: Placed prominently on the homepage with custom red progress bars and a "Resume" action.
- **Dedicated Watch History View**: Complete history timeline with progress bars, timestamps, resume buttons, individual item removal, and full history wipe.

### 5. 👥 Multi-Profile Support
- Built-in profile switcher with distinct avatar colors:
  - 🔴 **Default User**
  - 🔵 **Film Buff**
  - 🟣 **Sci-Fi Fan**
  - 🟢 **Guest**
- Each profile maintains completely isolated Watch History, Search History, Watchlist, and Personalized Recommendations.

### 6. 🛡️ Robust TMDB API Caching & Aesthetic Fallbacks
- Multi-tier caching: In-memory LRU cache + persistent SQLite database cache.
- Never breaks: If TMDB API is offline or rate-limited, an inline Netflix-themed SVG poster is dynamically generated with the movie title, release year, and genre.

---

## 📁 Project Architecture

```
netflix-movie-recommender/
│
├── main.py                     # FastAPI server, REST API endpoints, static mounting
├── engine.py                   # Recommendation engine, vector blending, multi-field search
├── database.py                 # SQLite persistence (profiles, watch history, search history, watchlist)
├── tmdb_service.py             # TMDB API client with caching and fallback SVG generation
├── build_metadata.py           # Precomputation script creating fast JSON metadata
│
├── static/                     # Frontend Single Page Application (SPA)
│   ├── index.html              # Main HTML5 layout (Hero, Carousels, Detail Modal, Toasts)
│   ├── css/
│   │   └── netflix.css         # Complete Netflix dark theme, sliders, modals, animations
│   └── js/
│       ├── api.js              # Asynchronous API fetch client
│       └── app.js              # State management, carousels, search auto-complete, playback
│
├── model/
│   ├── movie_list.pkl          # Processed DataFrame of 4,806 TMDB movies
│   ├── similarity.pkl          # Cosine similarity matrix (4806 x 4806)
│   └── movies_cache.json       # Precomputed rich metadata cache for instant lookups
│
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows batch launcher
├── run.ps1                     # PowerShell launcher
└── README_NEW.md               # Documentation & setup guide
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
- Python 3.10 or Python 3.11 installed.

### 1. Install Dependencies
Open PowerShell or Command Prompt in the project folder and run:
```bash
pip install -r requirements.txt
```

### 2. Verify Model & Dataset Files
Ensure the model files are located in the `model/` directory (or in `Downloads/`):
- `model/movie_list.pkl`
- `model/similarity.pkl`
- `model/movies_cache.json` *(already precomputed and included!)*

*(If you ever need to re-generate `movies_cache.json` from scratch, simply run `python build_metadata.py`)*

### 3. Start the Application
Run using the included script:
```powershell
.\run.ps1
```
Or directly with Uvicorn:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Open in Browser
Navigate to:
```
http://127.0.0.1:8000
```
Enjoy your personalized Netflix-style movie recommendation experience!

---

## 📡 REST API Documentation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the Netflix Single-Page Application |
| `GET` | `/api/profiles` | List all user profiles with avatar and active state |
| `POST` | `/api/profiles/select` | Switch the active profile |
| `GET` | `/api/movies/hero` | Get featured blockbuster for the top hero banner |
| `GET` | `/api/movies/carousels` | Get all homepage carousel rows (personalized & categorized) |
| `GET` | `/api/movies/search?q={query}` | Multi-attribute search across titles, cast, director, genres |
| `GET` | `/api/movies/{movie_id}` | Detailed movie information + trailer key + 5 recommendations |
| `GET` | `/api/history/watch` | Get watch history with playback progress percentages |
| `POST` | `/api/history/watch` | Record watched movie and progress |
| `DELETE` | `/api/history/watch/{id}` | Remove specific movie from watch history |
| `DELETE` | `/api/history/watch` | Clear entire watch history for active profile |
| `GET` | `/api/history/search` | Get logged search queries |
| `DELETE` | `/api/history/search/{id}` | Delete a specific search query |
| `DELETE` | `/api/history/search` | Clear all search queries |
| `GET` | `/api/watchlist` | Get saved watchlist |
| `POST` | `/api/watchlist/toggle` | Add/remove movie from watchlist |
| `GET` | `/api/recommendations/personalized` | Get vector-blended personalized recommendations |
| `GET` | `/api/status` | System health and model diagnostic status |

Interactive Swagger documentation is also available at:
```
http://127.0.0.1:8000/docs
```
