/**
 * app.js
 * Master UI controller for Netflix Movie Recommender application.
 * Manages states, carousels, modals, history views, and video playback.
 */

const App = {
  state: {
    activeView: 'home',
    currentProfile: null,
    profiles: [],
    heroMovie: null,
    carousels: [],
    searchDebounce: null,
    currentModalMovie: null
  },

  async init() {
    this.bindEvents();
    await this.loadProfiles();
    await this.loadHome();
  },

  bindEvents() {
    // Window scroll for navbar glassmorphism
    window.addEventListener('scroll', () => {
      const nav = document.getElementById('navbar');
      if (window.scrollY > 40) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    });

    // Profile Dropdown Toggle
    const pill = document.getElementById('profile-pill');
    const dropdown = document.getElementById('profile-dropdown');
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });

    document.addEventListener('click', () => {
      dropdown.classList.remove('open');
      document.getElementById('search-dropdown').classList.remove('open');
    });

    // Global Search Input with Debounce
    const searchInput = document.getElementById('global-search-input');
    const clearBtn = document.getElementById('search-clear-btn');

    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      clearBtn.style.display = q ? 'block' : 'none';

      clearTimeout(this.state.searchDebounce);
      if (q.length >= 2) {
        this.state.searchDebounce = setTimeout(() => {
          this.handleLiveSearch(q);
        }, 280);
      } else {
        document.getElementById('search-dropdown').classList.remove('open');
      }
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const q = searchInput.value.trim();
        if (q) {
          document.getElementById('search-dropdown').classList.remove('open');
          this.loadSearchResults(q);
        }
      }
    });

    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      clearBtn.style.display = 'none';
      document.getElementById('search-dropdown').classList.remove('open');
      if (this.state.activeView === 'search') {
        this.navigate('home');
      }
    });

    // Navigation Links
    document.querySelectorAll('[data-view]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const view = el.getAttribute('data-view');
        this.navigate(view);
      });
    });

    // Modal Close
    document.getElementById('modal-close-btn').addEventListener('click', () => {
      this.closeModal();
    });

    document.getElementById('movie-modal-overlay').addEventListener('click', (e) => {
      if (e.target.id === 'movie-modal-overlay') {
        this.closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeModal();
      }
    });
  },

  // ================= PROFILE MANAGEMENT =================
  async loadProfiles() {
    try {
      this.state.profiles = await API.getProfiles();
      this.state.currentProfile = await API.getActiveProfile();
      this.renderProfileUI();
    } catch (err) {
      console.error('Failed to load profiles:', err);
    }
  },

  renderProfileUI() {
    const cp = this.state.currentProfile;
    if (!cp) return;

    // Active pill
    const avatarEl = document.getElementById('active-avatar');
    avatarEl.className = `profile-avatar avatar-${cp.avatar}`;
    avatarEl.textContent = cp.name.charAt(0).toUpperCase();
    document.getElementById('active-profile-name').textContent = cp.name;

    // Dropdown items
    const listEl = document.getElementById('profile-list');
    listEl.innerHTML = '';
    this.state.profiles.forEach(p => {
      const opt = document.createElement('div');
      opt.className = `profile-option ${p.id === cp.id ? 'active' : ''}`;
      opt.innerHTML = `
        <div class="profile-avatar avatar-${p.avatar}">${p.name.charAt(0).toUpperCase()}</div>
        <span class="profile-name">${p.name}</span>
      `;
      opt.onclick = () => this.switchProfile(p.id);
      listEl.appendChild(opt);
    });
  },

  async switchProfile(profileId) {
    try {
      const res = await API.selectProfile(profileId);
      this.state.currentProfile = res.profile;
      this.renderProfileUI();
      this.showToast(`Switched to profile: ${res.profile.name}`);
      // Refresh current view
      if (this.state.activeView === 'home') {
        await this.loadHome();
      } else {
        await this.navigate(this.state.activeView);
      }
    } catch (err) {
      console.error('Profile switch error:', err);
    }
  },

  // ================= NAVIGATION =================
  async navigate(viewName) {
    this.state.activeView = viewName;

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(l => {
      if (l.getAttribute('data-view') === viewName) {
        l.classList.add('active');
      } else {
        l.classList.remove('active');
      }
    });

    const homeContainer = document.getElementById('home-view-container');
    const dynamicContainer = document.getElementById('dynamic-view-container');

    if (viewName === 'home') {
      homeContainer.style.display = 'block';
      dynamicContainer.style.display = 'none';
      await this.loadHome();
    } else {
      homeContainer.style.display = 'none';
      dynamicContainer.style.display = 'block';

      if (viewName === 'movies') {
        await this.loadAllMovies();
      } else if (viewName === 'toppicks') {
        await this.loadTopPicksView();
      } else if (viewName === 'watchlist') {
        await this.loadWatchlistView();
      } else if (viewName === 'history') {
        await this.loadWatchHistoryView();
      } else if (viewName === 'search_history') {
        await this.loadSearchHistoryView();
      }
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  // ================= HOME VIEW =================
  async loadHome() {
    try {
      // 1. Load Hero
      const hero = await API.getHeroMovie();
      this.state.heroMovie = hero;
      this.renderHero(hero);

      // 2. Load Carousels
      const carousels = await API.getCarousels();
      this.state.carousels = carousels;
      this.renderCarousels(carousels);
    } catch (err) {
      console.error('Failed to load home view:', err);
    }
  },

  renderHero(movie) {
    if (!movie) return;
    const banner = document.getElementById('hero-banner');
    banner.style.backgroundImage = `url('${movie.backdrop_url || movie.poster_url}')`;

    document.getElementById('hero-title').textContent = movie.title;
    document.getElementById('hero-match').textContent = `${movie.match_pct}% Match`;
    document.getElementById('hero-year').textContent = movie.year;
    document.getElementById('hero-runtime').textContent = movie.runtime;
    document.getElementById('hero-star').textContent = `★ ${movie.vote_average}`;
    document.getElementById('hero-overview').textContent = movie.overview;

    const playBtn = document.getElementById('hero-play-btn');
    playBtn.onclick = () => this.playMovie(movie.movie_id);

    const infoBtn = document.getElementById('hero-info-btn');
    infoBtn.onclick = () => this.openMovieModal(movie.movie_id);

    const wlBtn = document.getElementById('hero-watchlist-btn');
    this.updateWatchlistBtnState(wlBtn, movie.in_watchlist);
    wlBtn.onclick = () => this.toggleWatchlist(movie.movie_id, wlBtn);
  },

  renderCarousels(carousels) {
    const container = document.getElementById('carousels-container');
    container.innerHTML = '';

    carousels.forEach(row => {
      if (!row.movies || row.movies.length === 0) return;

      const rowEl = document.createElement('div');
      rowEl.className = 'carousel-row';
      rowEl.id = `row-${row.id}`;

      // Row Header
      const headerEl = document.createElement('div');
      headerEl.className = 'row-header';
      headerEl.innerHTML = `
        <h2 class="row-title">
          ${row.title}
          ${row.subtitle ? `<span class="row-subtitle">${row.subtitle}</span>` : ''}
        </h2>
      `;
      rowEl.appendChild(headerEl);

      // Slider Container
      const containerEl = document.createElement('div');
      containerEl.className = 'row-container';

      // Left Arrow
      const leftArrow = document.createElement('button');
      leftArrow.className = 'slider-arrow left';
      leftArrow.innerHTML = '‹';

      // Right Arrow
      const rightArrow = document.createElement('button');
      rightArrow.className = 'slider-arrow right';
      rightArrow.innerHTML = '›';

      // Movie Slider
      const sliderEl = document.createElement('div');
      sliderEl.className = 'movie-slider';

      leftArrow.onclick = () => {
        sliderEl.scrollBy({ left: -680, behavior: 'smooth' });
      };
      rightArrow.onclick = () => {
        sliderEl.scrollBy({ left: 680, behavior: 'smooth' });
      };

      row.movies.forEach(movie => {
        const card = this.createMovieCard(movie, row.type === 'continue_watching');
        sliderEl.appendChild(card);
      });

      containerEl.appendChild(leftArrow);
      containerEl.appendChild(sliderEl);
      containerEl.appendChild(rightArrow);

      rowEl.appendChild(containerEl);
      container.appendChild(rowEl);
    });
  },

  createMovieCard(movie, isContinueWatching = false) {
    const card = document.createElement('div');
    card.className = 'movie-card';

    const posterUrl = movie.poster_url || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="#222"/></svg>';

    card.innerHTML = `
      <img src="${posterUrl}" alt="${movie.title}" loading="lazy" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'200\\' height=\\'300\\'><rect width=\\'200\\' height=\\'300\\' fill=\\'#222\\'/><text x=\\'100\\' y=\\'150\\' fill=\\'#888\\' text-anchor=\\'middle\\'>Poster</text></svg>'">
      ${isContinueWatching ? `
        <div class="resume-tag">RESUME</div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill" style="width: ${movie.progress_pct || 30}%;"></div>
        </div>
      ` : ''}
      <div class="card-overlay">
        <div class="card-title">${movie.title}</div>
        <div class="card-meta">
          <span class="meta-match">${movie.match_pct || 90}%</span>
          <span class="meta-pill">${movie.year || '2015'}</span>
          <span class="meta-star">★ ${movie.vote_average || 7.0}</span>
        </div>
        <div class="card-actions">
          <button class="card-btn card-play" title="Play">▶</button>
          <button class="card-btn card-wl ${movie.in_watchlist ? 'in-watchlist' : ''}" title="Watchlist">
            ${movie.in_watchlist ? '✓' : '+'}
          </button>
          <button class="card-btn card-info" title="More Info">⌄</button>
        </div>
      </div>
    `;

    // Events
    card.querySelector('.card-play').onclick = (e) => {
      e.stopPropagation();
      this.playMovie(movie.movie_id);
    };

    const wlBtn = card.querySelector('.card-wl');
    wlBtn.onclick = (e) => {
      e.stopPropagation();
      this.toggleWatchlist(movie.movie_id, wlBtn);
    };

    card.querySelector('.card-info').onclick = (e) => {
      e.stopPropagation();
      this.openMovieModal(movie.movie_id);
    };

    card.onclick = () => {
      this.openMovieModal(movie.movie_id);
    };

    return card;
  },

  // ================= MOVIE DETAIL MODAL =================
  async openMovieModal(movieId) {
    try {
      const movie = await API.getMovieDetail(movieId);
      this.state.currentModalMovie = movie;

      const modalOverlay = document.getElementById('movie-modal-overlay');
      const banner = document.getElementById('modal-banner');
      banner.style.backgroundImage = `url('${movie.backdrop_url || movie.poster_url}')`;

      document.getElementById('modal-title').textContent = movie.title;
      document.getElementById('modal-tagline').textContent = movie.tagline || '';
      document.getElementById('modal-match').textContent = `${movie.match_pct || 92}% Match`;
      document.getElementById('modal-year').textContent = movie.year;
      document.getElementById('modal-runtime').textContent = movie.runtime;
      document.getElementById('modal-star').textContent = `★ ${movie.vote_average} (${movie.vote_count} votes)`;

      const playBtn = document.getElementById('modal-play-btn');
      playBtn.onclick = () => this.playMovie(movie.movie_id);

      const wlBtn = document.getElementById('modal-watchlist-btn');
      this.updateWatchlistBtnState(wlBtn, movie.in_watchlist);
      wlBtn.onclick = () => this.toggleWatchlist(movie.movie_id, wlBtn);

      document.getElementById('modal-overview').textContent = movie.overview;

      // Director & Cast
      document.getElementById('modal-director').textContent = movie.director || 'Unknown';
      document.getElementById('modal-cast').textContent = (movie.cast || []).join(', ') || 'N/A';

      // Genres
      const genresContainer = document.getElementById('modal-genres');
      genresContainer.innerHTML = '';
      (movie.genres || []).forEach(g => {
        const tag = document.createElement('span');
        tag.className = 'genre-tag';
        tag.textContent = g;
        genresContainer.appendChild(tag);
      });

      // Trailer embed
      const trailerBox = document.getElementById('modal-trailer-box');
      if (movie.trailer_key) {
        trailerBox.style.display = 'block';
        trailerBox.innerHTML = `
          <div class="trailer-container">
            <iframe src="https://www.youtube.com/embed/${movie.trailer_key}?autoplay=0&rel=0&modestbranding=1" allowfullscreen></iframe>
          </div>
        `;
      } else {
        trailerBox.style.display = 'none';
        trailerBox.innerHTML = '';
      }

      // Similar Recommendations (Top 5-6)
      const simContainer = document.getElementById('modal-similar-grid');
      simContainer.innerHTML = '';
      (movie.similar_recommendations || []).forEach(sim => {
        const simCard = document.createElement('div');
        simCard.className = 'similar-card';
        simCard.innerHTML = `
          <img src="${sim.poster_url}" alt="${sim.title}" loading="lazy">
          <div class="similar-info">
            <div class="similar-title">${sim.title}</div>
            <div class="similar-match">${sim.match_pct || 88}% Match</div>
          </div>
        `;
        simCard.onclick = () => {
          this.openMovieModal(sim.movie_id);
        };
        simContainer.appendChild(simCard);
      });

      modalOverlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    } catch (err) {
      console.error('Error opening movie modal:', err);
    }
  },

  closeModal() {
    const modalOverlay = document.getElementById('movie-modal-overlay');
    modalOverlay.classList.remove('open');
    document.body.style.overflow = 'auto';
    // Clear video to stop audio
    document.getElementById('modal-trailer-box').innerHTML = '';
  },

  // ================= PLAY MOVIE / VIDEO PLAYER =================
  async playMovie(movieId) {
    try {
      const movie = await API.getMovieDetail(movieId);
      // Automatically record watch history
      const progress = Math.floor(Math.random() * 40 + 25);
      await API.recordWatch(movieId, progress, `${progress}m of ${movie.runtime}`);

      this.showToast(`Now Playing: ${movie.title}`);

      // Open trailer in modal or fullscreen
      if (movie.trailer_key) {
        this.openMovieModal(movieId);
        const trailerBox = document.getElementById('modal-trailer-box');
        trailerBox.scrollIntoView({ behavior: 'smooth' });
        // Auto-play iframe
        trailerBox.innerHTML = `
          <div class="trailer-container">
            <iframe src="https://www.youtube.com/embed/${movie.trailer_key}?autoplay=1&rel=0" allow="autoplay; fullscreen" allowfullscreen></iframe>
          </div>
        `;
      } else {
        this.openMovieModal(movieId);
      }

      // Refresh background carousels so Continue Watching immediately shows!
      setTimeout(async () => {
        if (this.state.activeView === 'home') {
          const carousels = await API.getCarousels();
          this.state.carousels = carousels;
          this.renderCarousels(carousels);
        }
      }, 1000);
    } catch (err) {
      console.error('Error playing movie:', err);
    }
  },

  // ================= WATCHLIST =================
  async toggleWatchlist(movieId, btnElement) {
    try {
      const res = await API.toggleWatchlist(movieId);
      this.updateWatchlistBtnState(btnElement, res.is_saved);
      this.showToast(res.message);

      // If on watchlist view, refresh view
      if (this.state.activeView === 'watchlist') {
        await this.loadWatchlistView();
      }
    } catch (err) {
      console.error('Watchlist toggle error:', err);
    }
  },

  updateWatchlistBtnState(btn, isSaved) {
    if (!btn) return;
    if (isSaved) {
      btn.classList.add('in-watchlist');
      btn.innerHTML = btn.classList.contains('card-btn') ? '✓' : '✓ In Watchlist';
    } else {
      btn.classList.remove('in-watchlist');
      btn.innerHTML = btn.classList.contains('card-btn') ? '+' : '+ Watchlist';
    }
  },

  // ================= LIVE SEARCH & DROPDOWN =================
  async handleLiveSearch(query) {
    try {
      const res = await API.searchMovies(query);
      const dropdown = document.getElementById('search-dropdown');
      dropdown.innerHTML = '';

      if (!res.results || res.results.length === 0) {
        dropdown.innerHTML = `
          <div style="padding: 18px; text-align: center; color: #888; font-size: 13px;">
            No movies found matching "<b>${query}</b>"
          </div>
        `;
        dropdown.classList.add('open');
        return;
      }

      // Dropdown Title
      const title = document.createElement('div');
      title.className = 'dropdown-section-title';
      title.textContent = `Matching Results (${res.count})`;
      dropdown.appendChild(title);

      res.results.slice(0, 5).forEach(m => {
        const item = document.createElement('div');
        item.className = 'search-result-item';
        item.innerHTML = `
          <img src="${m.poster_url}" alt="${m.title}">
          <div class="search-result-info">
            <div class="search-result-title">${m.title}</div>
            <div class="search-result-meta">${m.year} • Dir: ${m.director} • ${m.genres ? m.genres.slice(0, 2).join(', ') : ''}</div>
          </div>
        `;
        item.onclick = () => {
          dropdown.classList.remove('open');
          this.openMovieModal(m.movie_id);
        };
        dropdown.appendChild(item);
      });

      // View All link
      const viewAll = document.createElement('div');
      viewAll.style.cssText = 'padding: 10px 14px; text-align: center; color: #E50914; font-size: 12px; font-weight: 700; cursor: pointer; border-top: 1px solid #282828;';
      viewAll.textContent = `View All ${res.count} Results →`;
      viewAll.onclick = () => {
        dropdown.classList.remove('open');
        this.loadSearchResults(query);
      };
      dropdown.appendChild(viewAll);

      dropdown.classList.add('open');
    } catch (err) {
      console.error('Search error:', err);
    }
  },

  async loadSearchResults(query) {
    this.state.activeView = 'search';
    document.getElementById('home-view-container').style.display = 'none';
    const dynContainer = document.getElementById('dynamic-view-container');
    dynContainer.style.display = 'block';

    dynContainer.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <h1 class="view-title">Search: "${query}"</h1>
          <span class="view-meta" id="search-count-header">Searching...</span>
        </div>
        <div class="movie-grid" id="search-grid"></div>
      </div>
    `;

    const res = await API.searchMovies(query);
    document.getElementById('search-count-header').textContent = `${res.count} movies found`;
    const grid = document.getElementById('search-grid');
    res.results.forEach(m => {
      grid.appendChild(this.createMovieCard(m));
    });
  },

  // ================= VIEW LOADERS =================
  async loadAllMovies() {
    const dyn = document.getElementById('dynamic-view-container');
    dyn.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <h1 class="view-title">All Movies Catalog</h1>
          <span class="view-meta">Explore 4,800+ TMDB Blockbusters & Hidden Gems</span>
        </div>
        <div style="display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap;" id="genre-filters">
          <button class="btn btn-small btn-primary" onclick="App.filterMoviesByGenre('All')">All</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Action')">Action</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Science Fiction')">Sci-Fi</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Adventure')">Adventure</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Drama')">Drama</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Comedy')">Comedy</button>
          <button class="btn btn-small btn-secondary" onclick="App.filterMoviesByGenre('Thriller')">Thriller</button>
        </div>
        <div class="movie-grid" id="all-movies-grid"></div>
      </div>
    `;
    this.filterMoviesByGenre('All');
  },

  async filterMoviesByGenre(genre) {
    const grid = document.getElementById('all-movies-grid');
    grid.innerHTML = '<div style="color: #888;">Loading movies...</div>';
    const res = await API.searchMovies(genre === 'All' ? 'the' : genre);
    grid.innerHTML = '';
    res.results.forEach(m => {
      grid.appendChild(this.createMovieCard(m));
    });
  },

  async loadTopPicksView() {
    const dyn = document.getElementById('dynamic-view-container');
    dyn.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <h1 class="view-title">Top Picks for You</h1>
          <span class="view-meta">Dynamic Vector Recommendations based on your Watch & Search Taste</span>
        </div>
        <div class="movie-grid" id="toppicks-grid"></div>
      </div>
    `;
    const recs = await API.getPersonalized();
    const grid = document.getElementById('toppicks-grid');
    recs.forEach(m => {
      grid.appendChild(this.createMovieCard(m));
    });
  },

  async loadWatchlistView() {
    const dyn = document.getElementById('dynamic-view-container');
    dyn.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <h1 class="view-title">My Watchlist</h1>
          <span class="view-meta" id="wl-count-header">Loading...</span>
        </div>
        <div class="movie-grid" id="watchlist-grid"></div>
      </div>
    `;
    const items = await API.getWatchlist();
    document.getElementById('wl-count-header').textContent = `${items.length} titles saved`;
    const grid = document.getElementById('watchlist-grid');
    if (items.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: #888;">
          <p style="font-size: 18px; margin-bottom: 12px;">Your Watchlist is empty.</p>
          <button class="btn btn-primary" onclick="App.navigate('home')">Explore Movies</button>
        </div>
      `;
      return;
    }
    items.forEach(m => {
      grid.appendChild(this.createMovieCard(m));
    });
  },

  async loadWatchHistoryView() {
    const dyn = document.getElementById('dynamic-view-container');
    dyn.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <div>
            <h1 class="view-title">Watch History & Continue Watching</h1>
            <span class="view-meta">Track your playback progress across sessions</span>
          </div>
          <button class="btn btn-secondary btn-small" onclick="App.clearAllWatchHistory()">Clear History</button>
        </div>
        <div class="history-list" id="history-list-container"></div>
      </div>
    `;

    const history = await API.getWatchHistory();
    const list = document.getElementById('history-list-container');
    if (history.length === 0) {
      list.innerHTML = `
        <div style="padding: 40px; text-align: center; color: #888;">
          <p style="font-size: 18px; margin-bottom: 12px;">No watch history recorded yet.</p>
          <button class="btn btn-primary" onclick="App.navigate('home')">Watch a Movie Now</button>
        </div>
      `;
      return;
    }

    history.forEach(item => {
      const el = document.createElement('div');
      el.className = 'history-item';
      el.innerHTML = `
        <div class="history-left">
          <img class="history-poster" src="${item.poster_url}" alt="${item.title}">
          <div>
            <div class="history-info-title">${item.title}</div>
            <div class="history-info-meta">
              Watched ${item.duration_watched || '30m'} (${item.progress_pct}% completed) • ${item.last_watched_at}
            </div>
            <div style="width: 200px; height: 3px; background: #333; margin-top: 6px; border-radius: 2px;">
              <div style="width: ${item.progress_pct}%; height: 100%; background: #E50914;"></div>
            </div>
          </div>
        </div>
        <div class="history-actions">
          <button class="btn btn-primary btn-small" onclick="App.playMovie(${item.movie_id})">▶ Resume</button>
          <button class="btn btn-secondary btn-small" onclick="App.deleteHistoryItem(${item.movie_id})">Remove</button>
        </div>
      `;
      list.appendChild(el);
    });
  },

  async deleteHistoryItem(movieId) {
    await API.deleteWatchHistory(movieId);
    this.showToast('Item removed from watch history');
    await this.loadWatchHistoryView();
  },

  async clearAllWatchHistory() {
    if (confirm('Are you sure you want to clear your entire watch history?')) {
      await API.clearWatchHistory();
      this.showToast('Watch history cleared');
      await this.loadWatchHistoryView();
    }
  },

  async loadSearchHistoryView() {
    const dyn = document.getElementById('dynamic-view-container');
    dyn.innerHTML = `
      <div class="view-container">
        <div class="view-header">
          <div>
            <h1 class="view-title">Search History</h1>
            <span class="view-meta">Recent queries used to personalize your movie recommendations</span>
          </div>
          <button class="btn btn-secondary btn-small" onclick="App.clearAllSearchHistory()">Clear Searches</button>
        </div>
        <div class="history-list" id="search-history-container"></div>
      </div>
    `;

    const searches = await API.getSearchHistory();
    const list = document.getElementById('search-history-container');
    if (searches.length === 0) {
      list.innerHTML = `
        <div style="padding: 40px; text-align: center; color: #888;">
          <p style="font-size: 18px; margin-bottom: 12px;">No search history found.</p>
        </div>
      `;
      return;
    }

    searches.forEach(item => {
      const el = document.createElement('div');
      el.className = 'history-item';
      el.innerHTML = `
        <div class="history-left">
          <div style="font-size: 20px;">🔍</div>
          <div>
            <div class="history-info-title">"${item.query}"</div>
            <div class="history-info-meta">${item.result_count} results found • ${item.searched_at}</div>
          </div>
        </div>
        <div class="history-actions">
          <button class="btn btn-primary btn-small" onclick="App.loadSearchResults('${item.query.replace(/'/g, "\\'")}')">Search Again</button>
          <button class="btn btn-secondary btn-small" onclick="App.deleteSearchItem(${item.id})">Remove</button>
        </div>
      `;
      list.appendChild(el);
    });
  },

  async deleteSearchItem(queryId) {
    await API.deleteSearchHistory(queryId);
    this.showToast('Search item removed');
    await this.loadSearchHistoryView();
  },

  async clearAllSearchHistory() {
    if (confirm('Clear all search history?')) {
      await API.clearSearchHistory();
      this.showToast('Search history cleared');
      await this.loadSearchHistoryView();
    }
  },

  // ================= TOAST NOTIFICATION =================
  showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2800);
  }
};

// Bootstrap application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
