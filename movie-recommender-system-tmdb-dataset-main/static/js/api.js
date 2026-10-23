/**
 * api.js
 * Asynchronous API client for Netflix Movie Recommender application.
 */

const API_BASE = '/api';

const API = {
  // Profiles
  async getProfiles() {
    const res = await fetch(`${API_BASE}/profiles`);
    return await res.json();
  },

  async getActiveProfile() {
    const res = await fetch(`${API_BASE}/profiles/active`);
    return await res.json();
  },

  async selectProfile(profileId) {
    const res = await fetch(`${API_BASE}/profiles/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_id: profileId })
    });
    return await res.json();
  },

  // Movies & Recommendations
  async getHeroMovie() {
    const res = await fetch(`${API_BASE}/movies/hero`);
    return await res.json();
  },

  async getCarousels() {
    const res = await fetch(`${API_BASE}/movies/carousels`);
    return await res.json();
  },

  async getMovieDetail(movieId) {
    const res = await fetch(`${API_BASE}/movies/${movieId}`);
    return await res.json();
  },

  async getPersonalized() {
    const res = await fetch(`${API_BASE}/recommendations/personalized`);
    return await res.json();
  },

  // Search & Autocomplete
  async searchMovies(query) {
    if (!query || !query.trim()) return { results: [] };
    const res = await fetch(`${API_BASE}/movies/search?q=${encodeURIComponent(query)}`);
    return await res.json();
  },

  // Watch History
  async getWatchHistory() {
    const res = await fetch(`${API_BASE}/history/watch`);
    return await res.json();
  },

  async recordWatch(movieId, progressPct = 30, durationWatched = "35m") {
    const res = await fetch(`${API_BASE}/history/watch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        movie_id: movieId,
        progress_pct: progressPct,
        duration_watched: durationWatched
      })
    });
    return await res.json();
  },

  async deleteWatchHistory(movieId) {
    const res = await fetch(`${API_BASE}/history/watch/${movieId}`, {
      method: 'DELETE'
    });
    return await res.json();
  },

  async clearWatchHistory() {
    const res = await fetch(`${API_BASE}/history/watch`, {
      method: 'DELETE'
    });
    return await res.json();
  },

  // Search History
  async getSearchHistory() {
    const res = await fetch(`${API_BASE}/history/search`);
    return await res.json();
  },

  async deleteSearchHistory(queryId) {
    const res = await fetch(`${API_BASE}/history/search/${queryId}`, {
      method: 'DELETE'
    });
    return await res.json();
  },

  async clearSearchHistory() {
    const res = await fetch(`${API_BASE}/history/search`, {
      method: 'DELETE'
    });
    return await res.json();
  },

  // Watchlist
  async getWatchlist() {
    const res = await fetch(`${API_BASE}/watchlist`);
    return await res.json();
  },

  async toggleWatchlist(movieId) {
    const res = await fetch(`${API_BASE}/watchlist/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie_id: movieId })
    });
    return await res.json();
  }
};
