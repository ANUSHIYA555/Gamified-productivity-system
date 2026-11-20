/**
 * FocusQuest - Gamified Productivity Web Application
 * Complete Reactive SPA Architecture
 */

const state = {
  currentUser: null,
  currentView: 'home',
  dashboard: null,
  tasks: [],
  activeSession: null,
  timerInterval: null,
  chatMessages: [],
  selectedTaskId: null,
  achievements: null,
  analytics: null,
  leaderboard: [],
  adminMetrics: null,
  adminLedger: [],
  learners: [],
  searchQuery: '',
  taskFilterStatus: 'All',
  taskFilterPriority: 'All',
  audioEnabled: true,
  timerDisplaySeconds: 0
};

// -------------------------------------------------------------
// WEB AUDIO SYNTHESIZER (FR-3.7)
// -------------------------------------------------------------
class SoundEngine {
  constructor() {
    this.ctx = null;
  }
  init() {
    if (!this.ctx && (window.AudioContext || window.webkitAudioContext)) {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
  }
  playChime() {
    try {
      this.init();
      if (!this.ctx || !state.audioEnabled) return;
      if (this.ctx.state === 'suspended') {
        this.ctx.resume();
      }
      const now = this.ctx.currentTime;
      // Multi-tone crystal harmonic chime
      const freqs = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
      freqs.forEach((f, i) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(f, now + i * 0.12);
        gain.gain.setValueAtTime(0.25, now + i * 0.12);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.12 + 1.2);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now + i * 0.12);
        osc.stop(now + i * 0.12 + 1.2);
      });
    } catch (e) {
      console.warn("Audio chime prevented or unsupported:", e);
    }
  }
}
const soundEngine = new SoundEngine();

// -------------------------------------------------------------
// CANVAS CONFETTI ENGINE (Celebration Animation)
// -------------------------------------------------------------
function fireCelebrationConfetti() {
  const canvas = document.getElementById('confetti-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const particles = [];
  const colors = ['#7c3aed', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ffffff'];

  for (let i = 0; i < 90; i++) {
    particles.push({
      x: canvas.width / 2,
      y: canvas.height / 2,
      vx: (Math.random() - 0.5) * 14,
      vy: (Math.random() - 0.7) * 16,
      size: Math.random() * 8 + 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 10,
      opacity: 1
    });
  }

  let frame = 0;
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;
    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.4; // gravity
      p.opacity -= 0.012;
      p.rotation += p.rotSpeed;

      if (p.opacity > 0) {
        alive = true;
        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
        ctx.restore();
      }
    });

    frame++;
    if (alive && frame < 120) {
      requestAnimationFrame(animate);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  animate();
}

// -------------------------------------------------------------
// TOAST NOTIFICATIONS & BROWSER NOTIFICATIONS (FR-3.7)
// -------------------------------------------------------------
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icon = type === 'success' ? '✨' : type === 'warning' ? '⚠️' : '💜';
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function triggerBrowserNotification(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, {
      body: body,
      icon: '/static/icons/star.png'
    });
  }
}

// -------------------------------------------------------------
// PAGE VISIBILITY DISTRACTION TRACKER (FR-3.9, NFR-3)
// -------------------------------------------------------------
document.addEventListener('visibilitychange', () => {
  if (document.hidden && state.activeSession && state.activeSession.status === 'running') {
    // User switched tabs during focus session!
    fetch('/api/timer/distraction/', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (state.activeSession) {
          state.activeSession.distraction_count = data.distraction_count;
          showToast(`Distraction logged (${data.distraction_count}x). Stay focused on your quest!`, 'warning');
          renderActiveView();
        }
      })
      .catch(err => console.error(err));
  }
});

// -------------------------------------------------------------
// API CLIENT
// -------------------------------------------------------------
async function api(endpoint, method = 'GET', body = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json'
    }
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  try {
    const res = await fetch(`/api${endpoint}`, options);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    showToast(err.message, 'warning');
    throw err;
  }
}

// -------------------------------------------------------------
// APP INITIALIZATION & NAVIGATION
// -------------------------------------------------------------
async function initApp() {
  try {
    // Load dashboard & active timer
    await loadDashboard();
    await checkActiveSession();
    setupEventListeners();
    startTimerTicker();
  } catch (e) {
    console.error("Initialization error:", e);
  }
}

async function loadDashboard() {
  const data = await api('/dashboard/');
  state.dashboard = data;
  state.currentUser = data.user;
  renderTopNav();
  renderActiveView();
}

async function checkActiveSession() {
  const res = await api('/timer/active/');
  state.activeSession = res.active_session;
  if (state.activeSession) {
    state.timerDisplaySeconds = state.activeSession.remaining_seconds;
  }
}

function setView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === viewName);
  });
  renderActiveView();
}

function renderActiveView() {
  const container = document.getElementById('view-content');
  if (!container) return;

  switch (state.currentView) {
    case 'home':
      container.innerHTML = renderHomeDashboardHTML();
      setupHomeInteractions();
      break;
    case 'tasks':
      loadTasksView(container);
      break;
    case 'pomodoro':
      loadPomodoroView(container);
      break;
    case 'achievements':
      loadAchievementsView(container);
      break;
    case 'leaderboard':
      loadLeaderboardView(container);
      break;
    case 'profile':
      loadProfileView(container);
      break;
    case 'settings':
      loadSettingsView(container);
      break;
    case 'assigner':
      loadAssignerView(container);
      break;
    case 'admin':
      loadAdminView(container);
      break;
    default:
      container.innerHTML = renderHomeDashboardHTML();
      setupHomeInteractions();
  }
}

// -------------------------------------------------------------
// TOP NAVBAR RENDERING
// -------------------------------------------------------------
function renderTopNav() {
  if (!state.currentUser) return;
  const user = state.currentUser;
  const avatarInitials = user.display_name ? user.display_name.substring(0, 2).toUpperCase() : 'AN';
  const headerAvatar = document.getElementById('header-avatar');
  if (headerAvatar) {
    headerAvatar.innerHTML = `<span class="avatar-initials">${avatarInitials}</span>`;
  }
}

// -------------------------------------------------------------
// VIEW 1: HOME DASHBOARD (Exact 1:1 Match to Screenshot)
// -------------------------------------------------------------
function renderHomeDashboardHTML() {
  if (!state.dashboard) return '<div style="padding: 40px; text-align: center;">Loading FocusQuest...</div>';

  const d = state.dashboard;
  const u = d.user;
  const p = d.progress_circle;
  const s = d.streak;
  const rw = d.next_reward;
  const lvl = u.level_info || { level: 12, current_level_xp: 720, next_level_xp: 1000, progress_percent: 72 };

  // Calculate greeting by hour
  const hour = new Date().getHours();
  const timeGreeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';

  // Donut SVG circumference calculation (r = 44)
  const radius = 44;
  const circ = 2 * Math.PI * radius;
  const strokeDashoffset = circ - (circ * (p.percent / 100));

  return `
    <div class="dashboard-top-row">
      <div class="greeting-text">
        <h2>${timeGreeting}, ${u.display_name}! ✨</h2>
        <p>Small steps. Big achievements. ✨</p>
      </div>

      <div class="level-widget">
        <div class="level-star-badge">
          <svg width="46" height="46" viewBox="0 0 46 46" fill="none">
            <polygon points="23,3 29,14 41,15 32,24 35,36 23,30 11,36 14,24 5,15 17,14" fill="url(#starGrad)" stroke="#f59e0b" stroke-width="1.5" />
            <circle cx="23" cy="22" r="7" fill="#78350f" stroke="#fbbf24" stroke-width="1.2" />
            <text x="23" y="25" text-anchor="middle" font-size="9" font-weight="bold" fill="#fff">★</text>
            <defs>
              <linearGradient id="starGrad" x1="0" y1="0" x2="46" y2="46" gradientUnits="userSpaceOnUse">
                <stop stop-color="#fbbf24"/>
                <stop offset="1" stop-color="#d97706"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div class="level-info">
          <div class="level-title-row">
            <span class="level-number">Level ${lvl.level}</span>
            <span class="level-xp-text">${lvl.current_level_xp} / ${lvl.next_level_xp} XP</span>
          </div>
          <div class="xp-progress-track">
            <div class="xp-progress-fill" style="width: ${lvl.progress_percent}%;"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="dashboard-grid">
      <!-- CARD 1: TODAY'S PROGRESS & MASCOT -->
      <div class="quest-card progress-card">
        <div class="card-header">
          <div class="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
            Today's Progress
          </div>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/></svg>
        </div>

        <div class="progress-card-content">
          <div class="progress-left">
            <div class="donut-ring-container">
              <svg width="110" height="110" viewBox="0 0 110 110">
                <circle cx="55" cy="55" r="${radius}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="11" />
                <circle cx="55" cy="55" r="${radius}" fill="none" stroke="url(#donutGrad)" stroke-width="11"
                  stroke-dasharray="${circ}" stroke-dashoffset="${strokeDashoffset}" stroke-linecap="round"
                  transform="rotate(-90 55 55)" />
                <defs>
                  <linearGradient id="donutGrad" x1="0" y1="0" x2="110" y2="110" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#c084fc"/>
                    <stop offset="1" stop-color="#6366f1"/>
                  </linearGradient>
                </defs>
              </svg>
              <div class="donut-text">${p.percent}%</div>
            </div>

            <div class="progress-stats-list">
              <div class="stat-item">
                <div class="stat-icon-wrap" style="background: rgba(168,85,247,0.2); color: #c084fc;">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <span>${p.tasks_str}</span>
              </div>
              <div class="stat-item">
                <div class="stat-icon-wrap" style="background: rgba(59,130,246,0.2); color: #60a5fa;">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <span>${p.focus_time_str} Focus Time</span>
              </div>
              <div class="stat-item">
                <div class="stat-icon-wrap" style="background: rgba(249,115,22,0.2); color: #fb923c;">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c-.6 3.5-3.5 5.5-4.5 8.5-1.5 4.5 1.5 9 6.5 9s7-4 5-8.5c-1.5-3.5-4.5-5-5-9z"/></svg>
                </div>
                <span>${p.xp_earned_today}</span>
              </div>
            </div>
          </div>

          <!-- KAWAII GAMER CAT MASCOT -->
          <div class="mascot-area">
            <div class="speech-bubble">
              ${d.mascot_message || "You're doing amazing! 💜"}
            </div>
            <div class="mascot-svg">
              <svg viewBox="0 0 180 160" width="100%" height="100%">
                <!-- Floating purple sparkles -->
                <text x="18" y="40" font-size="14" fill="#c084fc">✨</text>
                <text x="155" y="55" font-size="12" fill="#a855f7">✦</text>
                <text x="30" y="110" font-size="10" fill="#e879f9">✧</text>

                <!-- Headphones headband -->
                <path d="M 52 64 A 36 36 0 0 1 128 64" fill="none" stroke="#7c3aed" stroke-width="7" stroke-linecap="round" />
                <path d="M 56 64 A 32 32 0 0 1 124 64" fill="none" stroke="#a78bfa" stroke-width="3" />

                <!-- Kitty Ears -->
                <polygon points="50,48 40,20 72,36" fill="#f3e8ff" stroke="#7c3aed" stroke-width="2" />
                <polygon points="48,42 43,26 64,36" fill="#f472b6" />
                <polygon points="130,48 140,20 108,36" fill="#f3e8ff" stroke="#7c3aed" stroke-width="2" />
                <polygon points="132,42 137,26 116,36" fill="#f472b6" />

                <!-- Kitty Head -->
                <ellipse cx="90" cy="68" rx="42" ry="36" fill="#fdf4ff" stroke="#7c3aed" stroke-width="2.5" />

                <!-- Headphone Earcups with glowing neon lights -->
                <rect x="42" y="50" width="14" height="28" rx="7" fill="#581c87" stroke="#c084fc" stroke-width="2" />
                <circle cx="49" cy="64" r="3.5" fill="#a855f7" />
                <rect x="124" y="50" width="14" height="28" rx="7" fill="#581c87" stroke="#c084fc" stroke-width="2" />
                <circle cx="129" cy="64" r="3.5" fill="#a855f7" />

                <!-- Kitty Face (Kawaii Eyes, Nose, Mouth, Whiskers) -->
                <!-- Eyes: joyful curved arches ^.^ -->
                <path d="M 72 64 Q 78 58 84 64" fill="none" stroke="#3b0764" stroke-width="3" stroke-linecap="round" />
                <path d="M 96 64 Q 102 58 108 64" fill="none" stroke="#3b0764" stroke-width="3" stroke-linecap="round" />

                <!-- Cute rosy cheeks -->
                <ellipse cx="68" cy="74" rx="6" ry="3.5" fill="#f472b6" opacity="0.6" />
                <ellipse cx="112" cy="74" rx="6" ry="3.5" fill="#f472b6" opacity="0.6" />

                <!-- Tiny nose & mouth -->
                <polygon points="88,71 92,71 90,74" fill="#ec4899" />
                <path d="M 85 75 Q 90 79 90 76 Q 90 79 95 75" fill="none" stroke="#3b0764" stroke-width="2" stroke-linecap="round" />
                <!-- Cute smiling tongue -->
                <path d="M 87 77 Q 90 83 93 77 Z" fill="#f43f5e" />

                <!-- Whiskers -->
                <line x1="56" y1="72" x2="42" y2="70" stroke="#a855f7" stroke-width="1.5" stroke-linecap="round" />
                <line x1="56" y1="76" x2="44" y2="78" stroke="#a855f7" stroke-width="1.5" stroke-linecap="round" />
                <line x1="124" y1="72" x2="138" y2="70" stroke="#a855f7" stroke-width="1.5" stroke-linecap="round" />
                <line x1="124" y1="76" x2="136" y2="78" stroke="#a855f7" stroke-width="1.5" stroke-linecap="round" />

                <!-- Hoodie Body -->
                <path d="M 62 100 Q 90 94 118 100 L 126 135 L 54 135 Z" fill="#6b21a8" />
                <path d="M 78 98 L 90 115 L 102 98" fill="none" stroke="#a855f7" stroke-width="2" />

                <!-- Gamer Laptop with glowing crown -->
                <rect x="74" y="105" width="60" height="36" rx="4" fill="#1e1035" stroke="#9333ea" stroke-width="1.5" />
                <!-- Glowing Crown on Laptop lid -->
                <polygon points="104,116 100,125 108,125" fill="#c084fc" />
                <polygon points="101,118 96,125 106,125" fill="#c084fc" />
                <polygon points="107,118 102,125 112,125" fill="#c084fc" />

                <!-- Kitty paws typing -->
                <ellipse cx="78" cy="122" rx="7" ry="5" fill="#fdf4ff" stroke="#7c3aed" stroke-width="1.5" />
                <ellipse cx="112" cy="122" rx="7" ry="5" fill="#fdf4ff" stroke="#7c3aed" stroke-width="1.5" />

                <!-- Desk bar -->
                <rect x="30" y="134" width="130" height="6" rx="3" fill="#0f0926" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- CARD 2: STREAK CARD -->
      <div class="quest-card streak-card">
        <div class="streak-left">
          <h3>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#f97316"><path d="M12 2c-.6 3.5-3.5 5.5-4.5 8.5-1.5 4.5 1.5 9 6.5 9s7-4 5-8.5c-1.5-3.5-4.5-5-5-9z"/></svg>
            Streak
          </h3>
          <div class="streak-number-row">
            <span class="streak-val">${s.days}</span>
            <span class="streak-unit">Days</span>
          </div>
          <div class="streak-subtext">Keep going! 🔥</div>
        </div>

        <div class="streak-flame-graphic">
          <svg width="90" height="90" viewBox="0 0 100 100">
            <!-- Outer fire glow -->
            <circle cx="50" cy="55" r="35" fill="rgba(249,115,22,0.15)" filter="blur(10px)" />
            <!-- Large flame -->
            <path d="M 50 10 C 45 35 20 45 20 70 C 20 88 35 95 50 95 C 65 95 80 88 80 70 C 80 45 55 35 50 10 Z"
              fill="url(#fireOuter)" />
            <!-- Inner amber flame -->
            <path d="M 50 32 C 45 48 32 55 32 72 C 32 84 41 89 50 89 C 59 89 68 84 68 72 C 68 55 55 48 50 32 Z"
              fill="url(#fireInner)" />
            <!-- Bright core -->
            <path d="M 50 50 C 47 60 40 65 40 76 C 40 83 45 86 50 86 C 55 86 60 83 60 76 C 60 65 53 60 50 50 Z"
              fill="#fef08a" />
            <defs>
              <linearGradient id="fireOuter" x1="0" y1="0" x2="0" y2="100" gradientUnits="userSpaceOnUse">
                <stop stop-color="#ffedd5"/>
                <stop offset="0.3" stop-color="#fb923c"/>
                <stop offset="1" stop-color="#ea580c"/>
              </linearGradient>
              <linearGradient id="fireInner" x1="0" y1="30" x2="0" y2="90" gradientUnits="userSpaceOnUse">
                <stop stop-color="#fef08a"/>
                <stop offset="0.5" stop-color="#f59e0b"/>
                <stop offset="1" stop-color="#d97706"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
      </div>

      <!-- CARD 3: MY TASKS -->
      <div class="quest-card tasks-card">
        <div class="card-header">
          <div class="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            My Tasks
          </div>
          <button class="card-action-link" onclick="setView('tasks')">
            View All →
          </button>
        </div>

        <div class="task-list-simple">
          ${d.tasks.map(t => `
            <div class="task-row" data-task-id="${t.id}">
              <div class="task-row-left">
                <div class="custom-checkbox ${t.status === 'Done' ? 'checked' : ''}" onclick="toggleTaskDone(${t.id})">
                  ${t.status === 'Done' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="4"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
                </div>
                <span class="task-title-text ${t.status === 'Done' ? 'done' : ''}">${escapeHTML(t.title)}</span>
              </div>
              <span class="priority-pill ${t.priority.toLowerCase()}">${t.priority}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- CARD 4: WEEKLY OVERVIEW -->
      <div class="quest-card weekly-card">
        <div class="card-header">
          <div class="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Weekly Overview
          </div>
        </div>

        <div class="bar-chart-container">
          ${d.weekly_overview.map(col => {
            const heightPct = Math.max(18, Math.min(100, (col.minutes / 140) * 100));
            const isHighlight = col.day === 'Sun' || col.minutes >= 120;
            return `
              <div class="bar-col" title="${col.day}: ${col.minutes} mins">
                <div class="bar-tube ${isHighlight ? 'highlight' : ''}" style="height: ${heightPct}%;"></div>
                <span class="bar-label">${col.day}</span>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <!-- CARD 5: ACHIEVEMENTS -->
      <div class="quest-card achievements-card">
        <div class="card-header">
          <div class="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
            Achievements
          </div>
          <button class="card-action-link" onclick="setView('achievements')">
            View All →
          </button>
        </div>

        <div class="badge-row-display">
          ${d.featured_achievements.map(b => `
            <div class="badge-item" onclick="setView('achievements')" title="${b.unlock_rule}">
              <div class="badge-icon-shield ${b.badge_color}">
                ${renderBadgeIconSVG(b.icon)}
              </div>
              <span class="badge-name">${escapeHTML(b.name)}</span>
              <span class="badge-desc">${escapeHTML(b.description)}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- CARD 6: NEXT REWARD UNLOCKED -->
      <div class="quest-card reward-card">
        <div class="gift-box-graphic">
          <svg width="74" height="74" viewBox="0 0 90 90">
            <!-- Box base -->
            <rect x="18" y="38" width="54" height="42" rx="6" fill="#6d28d9" stroke="#c084fc" stroke-width="2" />
            <!-- Lid -->
            <rect x="14" y="30" width="62" height="12" rx="4" fill="#7c3aed" stroke="#e9d5ff" stroke-width="1.5" />
            <!-- Gold ribbon vertical -->
            <rect x="40" y="30" width="10" height="50" fill="#f59e0b" />
            <!-- Gold ribbon horizontal -->
            <rect x="18" y="52" width="54" height="8" fill="#f59e0b" />
            <!-- Golden Bow -->
            <ellipse cx="37" cy="24" rx="8" ry="6" fill="#fbbf24" stroke="#d97706" stroke-width="1.5" />
            <ellipse cx="53" cy="24" rx="8" ry="6" fill="#fbbf24" stroke="#d97706" stroke-width="1.5" />
            <circle cx="45" cy="26" r="4.5" fill="#f59e0b" />
            <!-- Sparkles -->
            <text x="8" y="24" font-size="12" fill="#fef08a">✦</text>
            <text x="72" y="30" font-size="14" fill="#fbbf24">✨</text>
          </svg>
        </div>

        <div class="reward-info">
          <div class="reward-title-row">
            <span>${rw.title}</span>
            <span>✨</span>
          </div>
          <p class="reward-desc">${rw.description}</p>
          <div class="reward-progress-track">
            <div class="reward-progress-fill" style="width: ${rw.current_percent}%;"></div>
          </div>
          <span class="reward-pct-text">${rw.current_percent}%</span>
        </div>
      </div>
    </div>
  `;
}

function renderBadgeIconSVG(icon) {
  if (icon === 'star') {
    return `<svg width="26" height="26" viewBox="0 0 24 24" fill="#fff"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`;
  } else if (icon === 'crown') {
    return `<svg width="26" height="26" viewBox="0 0 24 24" fill="#fff"><path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 14h14v2H5v-2z"/></svg>`;
  } else if (icon === 'calendar') {
    return `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><circle cx="8" cy="14" r="1.5" fill="#fff"/><circle cx="12" cy="14" r="1.5" fill="#fff"/><circle cx="16" cy="14" r="1.5" fill="#fff"/></svg>`;
  }
  return `<svg width="26" height="26" viewBox="0 0 24 24" fill="#fff"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>`;
}

function setupHomeInteractions() {
  // Any home specific binds
}

async function toggleTaskDone(taskId) {
  try {
    const res = await api(`/tasks/${taskId}/toggle_status/`, 'POST');
    if (res.awarded_xp > 0) {
      soundEngine.playChime();
      fireCelebrationConfetti();
      showToast(`+${res.awarded_xp} XP Earned! Level ${res.user_level_info.level}`, 'success');
    }
    if (res.unlocked_badges && res.unlocked_badges.length > 0) {
      res.unlocked_badges.forEach(b => {
        showToast(`🏆 New Badge Unlocked: ${b.name}!`, 'success');
      });
    }
    await loadDashboard();
  } catch (err) {
    console.error(err);
  }
}

// -------------------------------------------------------------
// VIEW 2: FULL TASKS SCREEN (FR-2.1 to FR-2.7)
// -------------------------------------------------------------
async function loadTasksView(container) {
  let url = `/tasks/?status=${state.taskFilterStatus}&priority=${state.taskFilterPriority}`;
  if (state.searchQuery) {
    url += `&search=${encodeURIComponent(state.searchQuery)}`;
  }
  const tasks = await api(url);
  state.tasks = tasks;

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <div>
        <h2 style="font-size: 26px; font-weight: 700;">Task Management</h2>
        <p style="color: var(--text-muted); font-size: 14px;">Organize, prioritize and conquer your quests.</p>
      </div>
      <button class="btn-primary" onclick="openAddTaskModal()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Create New Task
      </button>
    </div>

    <!-- FILTERS BAR -->
    <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;">
      <div style="display: flex; background: var(--bg-card); border-radius: 12px; padding: 4px; border: 1px solid var(--border-subtle);">
        ${['All', 'Today', 'To do', 'In progress', 'Done', 'Overdue'].map(st => `
          <button class="timer-mode-btn ${state.taskFilterStatus === st ? 'active' : ''}" onclick="setTaskFilterStatus('${st}')">
            ${st}
          </button>
        `).join('')}
      </div>

      <div style="display: flex; background: var(--bg-card); border-radius: 12px; padding: 4px; border: 1px solid var(--border-subtle);">
        ${['All', 'High', 'Medium', 'Low'].map(pr => `
          <button class="timer-mode-btn ${state.taskFilterPriority === pr ? 'active' : ''}" onclick="setTaskFilterPriority('${pr}')">
            ${pr}
          </button>
        `).join('')}
      </div>
    </div>

    <!-- TASKS CARDS -->
    <div style="display: grid; gap: 14px;">
      ${tasks.length === 0 ? `
        <div class="quest-card" style="text-align: center; padding: 48px;">
          <p style="color: var(--text-muted); font-size: 16px;">No tasks match this filter. Ready to forge a new quest?</p>
        </div>
      ` : tasks.map(t => `
        <div class="quest-card" style="padding: 18px 24px; display: flex; flex-direction: column; gap: 12px; border-left: 4px solid ${t.is_overdue ? '#ef4444' : t.priority === 'High' ? '#ec4899' : t.priority === 'Medium' ? '#f59e0b' : '#10b981'};">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="display: flex; align-items: center; gap: 14px;">
              <div class="custom-checkbox ${t.status === 'Done' ? 'checked' : ''}" onclick="toggleTaskDone(${t.id})">
                ${t.status === 'Done' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="4"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
              </div>
              <div>
                <h3 style="font-size: 16px; font-weight: 600; color: #fff; text-decoration: ${t.status === 'Done' ? 'line-through' : 'none'}; opacity: ${t.status === 'Done' ? '0.6' : '1'};">
                  ${escapeHTML(t.title)}
                  ${t.is_overdue ? '<span style="background: rgba(239,68,68,0.2); color: #f87171; font-size: 11px; padding: 2px 8px; border-radius: 8px; margin-left: 8px;">OVERDUE</span>' : ''}
                  ${t.assigned_by_name ? `<span style="background: rgba(59,130,246,0.2); color: #60a5fa; font-size: 11px; padding: 2px 8px; border-radius: 8px; margin-left: 8px;">Assigned by ${escapeHTML(t.assigned_by_name)}</span>` : ''}
                </h3>
                <p style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">${escapeHTML(t.description || 'No description provided.')}</p>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="priority-pill ${t.priority.toLowerCase()}">${t.priority}</span>
              <button class="btn-primary" style="padding: 7px 16px; font-size: 13px;" onclick="startFocusOnTask(${t.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Focus
              </button>
            </div>
          </div>

          <!-- SUBTASKS ACCORDION -->
          <div style="margin-top: 6px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.06);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">
                Subtasks (${t.subtasks.filter(st => st.done).length}/${t.subtasks.length})
              </span>
              <div style="display: flex; gap: 8px;">
                <button class="card-action-link" style="font-size: 12px;" onclick="requestGeminiBreakdown(${t.id})">
                  ✨ AI Step Breakdown
                </button>
                <button class="card-action-link" style="font-size: 12px;" onclick="promptAddSubtask(${t.id})">
                  + Add Subtask
                </button>
              </div>
            </div>

            <div style="display: flex; flex-direction: column; gap: 6px;">
              ${t.subtasks.map(st => `
                <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: ${st.done ? 'var(--text-dim)' : 'var(--text-main)'}; text-decoration: ${st.done ? 'line-through' : 'none'};">
                  <input type="checkbox" ${st.done ? 'checked' : ''} onchange="toggleSubtask(${st.id})" style="accent-color: #7c3aed; cursor: pointer;">
                  <span>${escapeHTML(st.title)}</span>
                  ${st.source === 'ai' ? '<span style="font-size: 10px; color: #a78bfa; background: rgba(167,139,250,0.15); padding: 1px 6px; border-radius: 6px;">AI Suggested</span>' : ''}
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function setTaskFilterStatus(st) {
  state.taskFilterStatus = st;
  renderActiveView();
}

function setTaskFilterPriority(pr) {
  state.taskFilterPriority = pr;
  renderActiveView();
}

async function toggleSubtask(subtaskId) {
  await api(`/subtasks/${subtaskId}/toggle/`, 'PATCH');
  renderActiveView();
}

async function promptAddSubtask(taskId) {
  const title = prompt("Enter subtask title:");
  if (title && title.trim()) {
    await api(`/tasks/${taskId}/subtasks/`, 'POST', { title: title.trim(), source: 'user' });
    renderActiveView();
  }
}

async function requestGeminiBreakdown(taskId) {
  showToast("Focus Coach is analyzing task and generating 25-minute steps...", "info");
  const res = await api(`/coach/breakdown/${taskId}/`, 'POST');
  if (res.steps && res.steps.length > 0) {
    const list = res.steps.map((s, i) => `${i + 1}. ${s.title} (~${s.estimated_minutes}m)`).join('\n');
    const accept = confirm(`Focus Coach suggests these structured steps:\n\n${list}\n\nAdd these steps to your subtask checklist?`);
    if (accept) {
      await api(`/coach/accept_breakdown/${taskId}/`, 'POST', { steps: res.steps });
      showToast("Steps added to checklist!", "success");
      renderActiveView();
    }
  }
}

function openAddTaskModal() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">Create New Quest Task</h3>
        <button class="modal-close-btn" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <form id="add-task-form" onsubmit="handleCreateTask(event)">
        <div class="form-group">
          <label>Task Title *</label>
          <input type="text" name="title" required class="form-control" placeholder="e.g. Master Linear Algebra chapter 3">
        </div>
        <div class="form-group">
          <label>Description</label>
          <textarea name="description" class="form-control" rows="3" placeholder="Key deliverables, lecture slides, formulas..."></textarea>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label>Priority</label>
            <select name="priority" class="form-control">
              <option value="High">High Priority (+30 XP)</option>
              <option value="Medium" selected>Medium Priority (+20 XP)</option>
              <option value="Low">Low Priority (+10 XP)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Due Date</label>
            <input type="date" name="due_date" class="form-control">
          </div>
        </div>
        <div style="display: flex; gap: 12px; margin-top: 20px;">
          <button type="submit" class="btn-primary" style="flex: 1; justify-content: center;">Add to Quest Log</button>
        </div>
      </form>
    </div>
  `;
  document.body.appendChild(modal);
}

async function handleCreateTask(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value.trim(),
    description: form.description.value.trim(),
    priority: form.priority.value,
    due_date: form.due_date.value || null,
    is_today: true
  };
  await api('/tasks/', 'POST', payload);
  showToast("New task created!", "success");
  form.closest('.modal-overlay').remove();
  await loadDashboard();
  renderActiveView();
}

function startFocusOnTask(taskId) {
  state.selectedTaskId = taskId;
  setView('pomodoro');
}

// -------------------------------------------------------------
// VIEW 3: POMODORO & GEMINI COACH FOCUS SCREEN (FR-3.1 to FR-3.9, FR-5.1 to FR-5.10)
// -------------------------------------------------------------
async function loadPomodoroView(container) {
  await checkActiveSession();
  const tasks = await api('/tasks/?status=To%20do');
  const allTasks = await api('/tasks/');
  const currentTask = allTasks.find(t => t.id === (state.activeSession ? state.activeSession.task : state.selectedTaskId)) || tasks[0] || allTasks[0];

  const session = state.activeSession;
  const isRunning = session && session.status === 'running';
  const isPaused = session && session.status === 'paused';
  const displaySecs = session ? session.remaining_seconds : (state.currentUser ? state.currentUser.focus_length_minutes * 60 : 1500);

  container.innerHTML = `
    <div class="focus-screen-wrapper">
      <!-- LEFT: TIMER CONTROLS (SRS 5.1: CLUTTER-FREE LARGE TIMER) -->
      <div class="timer-box">
        <!-- MODE SELECTOR -->
        <div class="timer-modes">
          <button class="timer-mode-btn ${(!session || session.session_type === 'focus') ? 'active' : ''}" onclick="selectTimerMode('focus')">
            Focus (25m)
          </button>
          <button class="timer-mode-btn ${session && session.session_type === 'short_break' ? 'active' : ''}" onclick="selectTimerMode('short_break')">
            Short Break (5m)
          </button>
          <button class="timer-mode-btn ${session && session.session_type === 'long_break' ? 'active' : ''}" onclick="selectTimerMode('long_break')">
            Long Break (15m)
          </button>
        </div>

        <!-- CURRENT LINKED TASK -->
        <div style="background: rgba(255,255,255,0.04); border: 1px solid var(--border-subtle); border-radius: 14px; padding: 12px 20px; width: 100%; margin-bottom: 24px; text-align: left; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <span style="font-size: 11px; color: var(--purple-light); font-weight: 600; text-transform: uppercase;">Active Quest Task</span>
            <h4 style="font-size: 15px; font-weight: 600; color: #fff; margin-top: 2px;">
              ${currentTask ? escapeHTML(currentTask.title) : 'No Task Selected'}
            </h4>
          </div>
          ${currentTask ? `<span class="priority-pill ${currentTask.priority.toLowerCase()}">${currentTask.priority}</span>` : ''}
        </div>

        <!-- BIG CIRCULAR COUNTDOWN TIMER -->
        <div class="big-timer-circle">
          <div class="big-timer-display" id="timer-number-display">
            ${formatTimerDisplay(displaySecs)}
          </div>
          <div class="timer-subtext">
            ${isRunning ? '🔥 Focus Running' : isPaused ? '⏸ Paused' : 'Ready to Focus'}
          </div>
        </div>

        <!-- SESSION CONTROLS (FR-3.3) -->
        <div class="timer-controls-row">
          ${!isRunning && !isPaused ? `
            <button class="btn-primary" onclick="handleStartTimer(${currentTask ? currentTask.id : 'null'})">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Start Session
            </button>
          ` : isRunning ? `
            <button class="btn-secondary" onclick="handlePauseTimer()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              Pause
            </button>
            <button class="btn-primary" onclick="openSessionOutcomeModal()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
              Finish Session
            </button>
            <button class="btn-secondary" style="color: #f87171;" onclick="handleStopTimer()">
              Abandon
            </button>
          ` : `
            <button class="btn-primary" onclick="handleResumeTimer()">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Resume
            </button>
            <button class="btn-primary" onclick="openSessionOutcomeModal()">
              Finish Session
            </button>
            <button class="btn-secondary" style="color: #f87171;" onclick="handleStopTimer()">
              Abandon
            </button>
          `}
        </div>

        ${session && session.session_type !== 'focus' ? `
          <button class="card-action-link" style="margin-top: 10px;" onclick="handleSkipBreak()">
            Skip Break →
          </button>
        ` : ''}

        <!-- DISTRACTION COUNTER (FR-3.9) -->
        ${session && session.distraction_count > 0 ? `
          <div class="distraction-banner" style="margin-top: 16px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>Tab switches detected: <strong>${session.distraction_count} distractions</strong></span>
          </div>
        ` : ''}
      </div>

      <!-- RIGHT: GEMINI FOCUS COACH PANEL (FR-5.1 to FR-5.10) -->
      <div class="coach-panel">
        <div class="coach-header">
          <div class="coach-header-left">
            <div class="coach-avatar">
              <span style="font-size: 18px;">🐱</span>
            </div>
            <div class="coach-title">
              <h4>Focus Coach (Gemini)</h4>
              <p>On-task AI guide • 30 msgs/hr quota</p>
            </div>
          </div>
          <button class="card-action-link" style="font-size: 12px;" onclick="clearCoachHistory(${currentTask ? currentTask.id : 'null'})">
            Clear Chat
          </button>
        </div>

        <div class="coach-messages" id="coach-messages-box">
          <div class="chat-bubble coach">
            Hello! I'm your Gemini Focus Coach. I stay dedicated to your current task '${currentTask ? escapeHTML(currentTask.title) : 'your work'}' and keep you in deep flow. How can we make rapid progress right now?
          </div>
          <!-- Loaded messages will append here -->
        </div>

        <!-- QUICK PROMPT CHIPS -->
        <div style="padding: 6px 16px; display: flex; gap: 6px; overflow-x: auto; background: rgba(18, 14, 40, 0.8);">
          <button class="timer-mode-btn" style="padding: 4px 10px; font-size: 11px;" onclick="sendCoachQuickMsg('Suggest a concrete first step for this task')">
            🎯 Suggest First Step
          </button>
          <button class="timer-mode-btn" style="padding: 4px 10px; font-size: 11px;" onclick="sendCoachQuickMsg('Break this into small 25-minute sprints')">
            ⚡ Sprint Plan
          </button>
          <button class="timer-mode-btn" style="padding: 4px 10px; font-size: 11px;" onclick="sendCoachQuickMsg('Give me a 30-second focus motivation boost!')">
            🔥 Motivation
          </button>
        </div>

        <!-- CHAT INPUT -->
        <div class="coach-input-area">
          <input type="text" id="coach-input" placeholder="Ask your coach anything about this task..." onkeydown="if(event.key==='Enter') sendCoachMessage(${currentTask ? currentTask.id : 'null'})">
          <button onclick="sendCoachMessage(${currentTask ? currentTask.id : 'null'})">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
    </div>
  `;

  if (currentTask) {
    loadCoachChatHistory(currentTask.id);
  }
}

function formatTimerDisplay(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function startTimerTicker() {
  if (state.timerInterval) clearInterval(state.timerInterval);
  state.timerInterval = setInterval(() => {
    if (state.activeSession && state.activeSession.status === 'running') {
      if (state.timerDisplaySeconds > 0) {
        state.timerDisplaySeconds--;
        const el = document.getElementById('timer-number-display');
        if (el) {
          el.innerText = formatTimerDisplay(state.timerDisplaySeconds);
        }
        // Browser tab title update (FR-3.8)
        document.title = `(${formatTimerDisplay(state.timerDisplaySeconds)}) FocusQuest`;
      } else {
        // Session ended naturally!
        soundEngine.playChime();
        triggerBrowserNotification("Focus Session Complete! 🎉", "Great job! Time to record your outcome and claim your XP!");
        openSessionOutcomeModal();
      }
    } else {
      document.title = "FocusQuest - Plan • Focus • Level Up";
    }
  }, 1000);
}

async function handleStartTimer(taskId) {
  if (!taskId) {
    showToast("Please choose or create a task first!", "warning");
    return;
  }
  const session = await api('/timer/start/', 'POST', { task_id: taskId });
  state.activeSession = session;
  state.timerDisplaySeconds = session.planned_minutes * 60;
  showToast("Focus session started! Deep work begins now.", "success");
  renderActiveView();
}

async function handlePauseTimer() {
  const session = await api('/timer/pause/', 'POST');
  state.activeSession = session;
  renderActiveView();
}

async function handleResumeTimer() {
  const session = await api('/timer/resume/', 'POST');
  state.activeSession = session;
  renderActiveView();
}

async function handleStopTimer() {
  const conf = confirm("Abandon this focus session? (Abandoned sessions earn no XP)");
  if (conf) {
    await api('/timer/stop/', 'POST');
    state.activeSession = null;
    showToast("Session abandoned.", "info");
    renderActiveView();
  }
}

async function handleSkipBreak() {
  await api('/timer/skip_break/', 'POST');
  state.activeSession = null;
  renderActiveView();
}

function selectTimerMode(mode) {
  // Sets default mode
  showToast(`Timer mode set to ${mode.replace('_', ' ')}`, "info");
}

function openSessionOutcomeModal() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">🎉 Session Completed!</h3>
        <button class="modal-close-btn" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 16px;">
        Record your progress outcome to calculate XP rewards and update your streak:
      </p>

      <div class="outcome-options">
        <button class="outcome-btn selected" id="outcome-done" onclick="selectOutcome('task_done')">
          <span style="font-size: 24px;">✅</span>
          <span>Task Done!</span>
          <span style="font-size: 11px; color: #34d399;">+ Task Bonus XP</span>
        </button>
        <button class="outcome-btn" id="outcome-progress" onclick="selectOutcome('more_work_needed')">
          <span style="font-size: 24px;">⚡</span>
          <span>More Needed</span>
          <span style="font-size: 11px; color: #fbbf24;">+ Session XP</span>
        </button>
        <button class="outcome-btn" id="outcome-blocked" onclick="selectOutcome('blocked')">
          <span style="font-size: 24px;">🛑</span>
          <span>Blocked</span>
          <span style="font-size: 11px; color: #f87171;">Save Progress</span>
        </button>
      </div>

      <button class="btn-primary" style="width: 100%; justify-content: center; margin-top: 10px;" onclick="submitSessionOutcome()">
        Claim Rewards & Level Up!
      </button>
    </div>
  `;
  document.body.appendChild(modal);
}

let selectedOutcomeVal = 'task_done';
function selectOutcome(val) {
  selectedOutcomeVal = val;
  document.querySelectorAll('.outcome-btn').forEach(b => b.classList.remove('selected'));
  const el = val === 'task_done' ? document.getElementById('outcome-done') : val === 'more_work_needed' ? document.getElementById('outcome-progress') : document.getElementById('outcome-blocked');
  if (el) el.classList.add('selected');
}

async function submitSessionOutcome() {
  try {
    const res = await api('/timer/complete/', 'POST', { outcome: selectedOutcomeVal });
    soundEngine.playChime();
    fireCelebrationConfetti();
    document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
    showToast(`Session Completed! +${res.earned_xp} XP earned! Streak: ${res.streak} days 🔥`, "success");
    if (res.unlocked_badges && res.unlocked_badges.length > 0) {
      res.unlocked_badges.forEach(b => {
        showToast(`🏆 Badge Unlocked: ${b.name}!`, 'success');
      });
    }
    state.activeSession = null;
    await loadDashboard();
    renderActiveView();
  } catch (err) {
    console.error(err);
  }
}

// -------------------------------------------------------------
// AI COACH CHAT LOGIC (FR-5.1 to FR-5.10)
// -------------------------------------------------------------
async function loadCoachChatHistory(taskId) {
  if (!taskId) return;
  const history = await api(`/coach/history/${taskId}/`);
  const box = document.getElementById('coach-messages-box');
  if (!box) return;

  history.forEach(msg => {
    appendCoachBubble(msg.role, msg.content, msg.id, msg.thumbs_rating);
  });
  box.scrollTop = box.scrollHeight;
}

function appendCoachBubble(role, content, msgId = null, rating = 'none') {
  const box = document.getElementById('coach-messages-box');
  if (!box) return;
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${role}`;
  bubble.innerHTML = `
    <div>${escapeHTML(content)}</div>
    ${role === 'coach' && msgId ? `
      <div class="bubble-rating">
        <button class="rate-btn ${rating === 'up' ? 'active' : ''}" onclick="rateCoachMsg(${msgId}, 'up', this)">👍</button>
        <button class="rate-btn ${rating === 'down' ? 'active' : ''}" onclick="rateCoachMsg(${msgId}, 'down', this)">👎</button>
      </div>
    ` : ''}
  `;
  box.appendChild(bubble);
  box.scrollTop = box.scrollHeight;
}

async function sendCoachMessage(taskId) {
  const input = document.getElementById('coach-input');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  appendCoachBubble('user', text);

  try {
    const res = await api('/coach/chat/', 'POST', { message: text, task_id: taskId });
    appendCoachBubble('coach', res.coach_message.content, res.coach_message.id, 'none');
  } catch (e) {
    appendCoachBubble('coach', "The Focus Coach had a network hiccup, but keep going strong on your task!");
  }
}

function sendCoachQuickMsg(text) {
  const input = document.getElementById('coach-input');
  if (input) {
    input.value = text;
    sendCoachMessage(state.selectedTaskId);
  }
}

async function rateCoachMsg(msgId, rating, btn) {
  await api(`/coach/rate/${msgId}/`, 'POST', { rating });
  btn.classList.add('active');
  showToast("Feedback noted!", "info");
}

async function clearCoachHistory(taskId) {
  if (!taskId) return;
  await api(`/coach/clear/${taskId}/`, 'POST');
  const box = document.getElementById('coach-messages-box');
  if (box) {
    box.innerHTML = `<div class="chat-bubble coach">Chat history cleared. What task shall we conquer next?</div>`;
  }
  showToast("Chat history cleared.", "info");
}

// -------------------------------------------------------------
// VIEW 4: ACHIEVEMENTS & XP LEDGER (FR-4.6, FR-4.8)
// -------------------------------------------------------------
async function loadAchievementsView(container) {
  const data = await api('/achievements/');
  const badges = data.badges;
  const ledger = data.xp_ledger;
  const lvl = data.level_info;

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <div>
        <h2 style="font-size: 26px; font-weight: 700;">Achievements & Rewards</h2>
        <p style="color: var(--text-muted); font-size: 14px;">Unlock badges, level up, and inspect your XP ledger.</p>
      </div>
      <div style="background: var(--bg-card); border: 1px solid rgba(245,158,11,0.3); border-radius: 14px; padding: 10px 20px; display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 24px;">🏆</span>
        <div>
          <span style="font-size: 16px; font-weight: 700; color: #fff;">Level ${lvl.level} Adventurer</span>
          <p style="font-size: 12px; color: var(--gold-accent);">${lvl.total_xp} Total XP</p>
        </div>
      </div>
    </div>

    <!-- ALL BADGES GRID -->
    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 14px; color: #fff;">Badge Hall</h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-bottom: 36px;">
      ${badges.map(b => `
        <div class="quest-card" style="opacity: ${b.is_earned ? '1' : '0.55'}; border-color: ${b.is_earned ? 'var(--border-glow)' : 'rgba(255,255,255,0.06)'}; text-align: center; padding: 20px;">
          <div class="badge-icon-shield ${b.badge_color}" style="margin: 0 auto 12px auto;">
            ${renderBadgeIconSVG(b.icon)}
          </div>
          <h4 style="font-size: 15px; font-weight: 700; color: #fff;">${escapeHTML(b.name)}</h4>
          <p style="font-size: 12px; color: var(--text-muted); margin: 6px 0 10px 0;">${escapeHTML(b.description)}</p>
          <span style="font-size: 11px; font-weight: 600; color: ${b.is_earned ? '#34d399' : '#a855f7'}; background: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 12px;">
            ${b.is_earned ? '✓ Unlocked (+ ' + b.xp_reward + ' XP)' : '🔒 ' + b.unlock_rule}
          </span>
        </div>
      `).join('')}
    </div>

    <!-- XP AUDIT LEDGER (FR-4.8) -->
    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 14px; color: #fff;">XP Audit Ledger (Server Validated)</h3>
    <div class="quest-card" style="padding: 16px 20px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13.5px; text-align: left;">
        <thead>
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted);">
            <th style="padding: 10px 12px;">Timestamp</th>
            <th style="padding: 10px 12px;">Action / Reason</th>
            <th style="padding: 10px 12px;">Task</th>
            <th style="padding: 10px 12px; text-align: right;">XP Change</th>
          </tr>
        </thead>
        <tbody>
          ${ledger.map(e => `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
              <td style="padding: 10px 12px; color: var(--text-dim);">${new Date(e.created_at).toLocaleString()}</td>
              <td style="padding: 10px 12px; color: #fff; font-weight: 500;">${escapeHTML(e.reason)}</td>
              <td style="padding: 10px 12px; color: var(--purple-light);">${escapeHTML(e.task_title || '-')}</td>
              <td style="padding: 10px 12px; text-align: right; color: #34d399; font-weight: 700;">+${e.amount} XP</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// -------------------------------------------------------------
// VIEW 5: LEADERBOARD
// -------------------------------------------------------------
async function loadLeaderboardView(container) {
  const learners = await api('/leaderboard/');
  container.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 26px; font-weight: 700;">Global Leaderboard</h2>
      <p style="color: var(--text-muted); font-size: 14px;">Compete with fellow learners on XP and consistent streaks.</p>
    </div>

    <div class="quest-card" style="padding: 16px 20px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 14px; text-align: left;">
        <thead>
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted);">
            <th style="padding: 12px;">Rank</th>
            <th style="padding: 12px;">Learner</th>
            <th style="padding: 12px;">Level</th>
            <th style="padding: 12px;">Streak</th>
            <th style="padding: 12px;">Badges</th>
            <th style="padding: 12px; text-align: right;">Total XP</th>
          </tr>
        </thead>
        <tbody>
          ${learners.map(l => `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
              <td style="padding: 12px; font-weight: 700; color: ${l.rank === 1 ? '#fbbf24' : l.rank === 2 ? '#e2e8f0' : l.rank === 3 ? '#d97706' : 'var(--text-muted)'};">
                ${l.rank === 1 ? '🥇 #1' : l.rank === 2 ? '🥈 #2' : l.rank === 3 ? '🥉 #3' : '#' + l.rank}
              </td>
              <td style="padding: 12px; display: flex; align-items: center; gap: 10px; font-weight: 600; color: #fff;">
                <span style="width: 32px; height: 32px; border-radius: 50%; background: #6b21a8; display: inline-flex; align-items: center; justify-content: center; font-size: 12px;">
                  ${l.display_name.substring(0, 2).toUpperCase()}
                </span>
                ${escapeHTML(l.display_name)}
              </td>
              <td style="padding: 12px; color: var(--purple-light); font-weight: 600;">Level ${l.level}</td>
              <td style="padding: 12px; color: #fb923c; font-weight: 600;">🔥 ${l.streak} d</td>
              <td style="padding: 12px; color: #34d399;">🏆 ${l.badge_count}</td>
              <td style="padding: 12px; text-align: right; font-weight: 800; color: #fff;">${l.total_xp} XP</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// -------------------------------------------------------------
// VIEW 6: USER PROFILE & ROLE SWITCHER (FR-1.2, FR-1.3)
// -------------------------------------------------------------
async function loadProfileView(container) {
  const user = state.currentUser;
  container.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 26px; font-weight: 700;">User Profile</h2>
      <p style="color: var(--text-muted); font-size: 14px;">Manage identity, focus preferences, and test system roles.</p>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
      <div class="quest-card">
        <h3 style="font-size: 17px; font-weight: 600; margin-bottom: 18px;">Profile Information</h3>
        <form onsubmit="handleUpdateProfile(event)">
          <div class="form-group">
            <label>Display Name</label>
            <input type="text" name="display_name" class="form-control" value="${escapeHTML(user.display_name)}">
          </div>
          <div class="form-group">
            <label>Current Role (FR-1.3)</label>
            <select name="role" class="form-control" onchange="handleRoleSwitch(this.value)">
              <option value="Learner" ${user.role === 'Learner' ? 'selected' : ''}>Learner (Primary student mode)</option>
              <option value="Task Assigner" ${user.role === 'Task Assigner' ? 'selected' : ''}>Task Assigner (Teacher / Mentor mode)</option>
              <option value="Administrator" ${user.role === 'Administrator' ? 'selected' : ''}>Administrator (System management)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Daily Focus Goal (Minutes, default 120)</label>
            <input type="number" name="daily_goal_minutes" class="form-control" value="${user.daily_goal_minutes}">
          </div>
          <button type="submit" class="btn-primary" style="margin-top: 10px;">Save Profile</button>
        </form>
      </div>

      <div class="quest-card">
        <h3 style="font-size: 17px; font-weight: 600; margin-bottom: 18px;">Gamification Status</h3>
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div class="task-row">
            <span>Current Level</span>
            <strong style="color: var(--purple-light);">Level ${user.level}</strong>
          </div>
          <div class="task-row">
            <span>Total XP</span>
            <strong style="color: #34d399;">${user.total_xp} XP</strong>
          </div>
          <div class="task-row">
            <span>Current Streak</span>
            <strong style="color: #fb923c;">🔥 ${user.current_streak} Days</strong>
          </div>
          <div class="task-row">
            <span>Weekly Streak Freeze (FR-4.9)</span>
            <strong style="color: ${user.streak_freeze_available ? '#34d399' : '#f87171'};">
              ${user.streak_freeze_available ? '🛡️ Available (1/1)' : 'Used this week'}
            </strong>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function handleUpdateProfile(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    display_name: form.display_name.value.trim(),
    role: form.role.value,
    daily_goal_minutes: form.daily_goal_minutes.value
  };
  const updated = await api('/auth/profile/', 'PUT', payload);
  state.currentUser = updated;
  showToast("Profile settings saved!", "success");
  await loadDashboard();
}

async function handleRoleSwitch(newRole) {
  await api('/auth/profile/', 'PATCH', { role: newRole });
  showToast(`Switched active role to: ${newRole}`, "info");
  await loadDashboard();
  renderActiveView();
}

// -------------------------------------------------------------
// VIEW 7: SETTINGS & CSV EXPORT (FR-1.2, FR-6.4, NFR-5)
// -------------------------------------------------------------
async function loadSettingsView(container) {
  container.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 26px; font-weight: 700;">Settings & Integration</h2>
      <p style="color: var(--text-muted); font-size: 14px;">Configure AI engine, audio, notifications, and export data.</p>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
      <div class="quest-card">
        <h3 style="font-size: 17px; font-weight: 600; margin-bottom: 14px;">AI Coach Engine (Gemini)</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">
          The system uses Google Gemini API with fallback rules (FR-5.8). Gemini API key is kept securely on the server (NFR-5).
        </p>
        <div class="form-group">
          <label>Configured Model</label>
          <input type="text" readonly class="form-control" value="gemini-2.5-flash (Low-latency configured)">
        </div>
        <div class="form-group">
          <label>Test Sound Synthesizer (FR-3.7)</label>
          <button type="button" class="btn-secondary" onclick="soundEngine.playChime()">
            🔊 Play End-of-Session Crystal Chime
          </button>
        </div>
        <div class="form-group">
          <label>Desktop Notifications (FR-3.7)</label>
          <button type="button" class="btn-secondary" onclick="requestNotificationPermission()">
            🔔 Request Browser Notification Permission
          </button>
        </div>
      </div>

      <div class="quest-card">
        <h3 style="font-size: 17px; font-weight: 600; margin-bottom: 14px;">Data Management & Export</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
          Export your entire focus session history for external analysis or compliance.
        </p>
        <a href="/api/analytics/export_csv/" download="focusquest_sessions.csv" class="btn-primary" style="text-decoration: none; display: inline-flex;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export Sessions as CSV (FR-6.4)
        </a>
      </div>
    </div>
  `;
}

function requestNotificationPermission() {
  if ('Notification' in window) {
    Notification.requestPermission().then(perm => {
      showToast(`Notification permission: ${perm}`, "info");
      if (perm === 'granted') {
        triggerBrowserNotification("FocusQuest Notifications Enabled", "You will now receive alerts when your focus sessions complete!");
      }
    });
  } else {
    showToast("Notifications not supported in this browser.", "warning");
  }
}

// -------------------------------------------------------------
// VIEW 8: TASK ASSIGNER PORTAL (FR-2.4)
// -------------------------------------------------------------
async function loadAssignerView(container) {
  const learners = await api('/learners/');
  container.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 26px; font-weight: 700;">Task Assigner Portal</h2>
      <p style="color: var(--text-muted); font-size: 14px;">Assign tasks directly to learners (FR-2.4).</p>
    </div>

    <div class="quest-card" style="max-width: 650px;">
      <form onsubmit="handleAssignTask(event)">
        <div class="form-group">
          <label>Assign to Learner *</label>
          <select name="learner_id" class="form-control" required>
            ${learners.map(l => `<option value="${l.id}">${escapeHTML(l.display_name)} (${escapeHTML(l.email)})</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label>Task Title *</label>
          <input type="text" name="title" class="form-control" required placeholder="e.g. Complete Lab Assignment 4">
        </div>
        <div class="form-group">
          <label>Description & Requirements</label>
          <textarea name="description" class="form-control" rows="3"></textarea>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label>Priority</label>
            <select name="priority" class="form-control">
              <option value="High">High</option>
              <option value="Medium" selected>Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <div class="form-group">
            <label>Due Date</label>
            <input type="date" name="due_date" class="form-control">
          </div>
        </div>
        <button type="submit" class="btn-primary" style="margin-top: 14px;">Assign Task to Learner</button>
      </form>
    </div>
  `;
}

async function handleAssignTask(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    learner_id: form.learner_id.value,
    title: form.title.value.trim(),
    description: form.description.value.trim(),
    priority: form.priority.value,
    due_date: form.due_date.value || null
  };
  await api('/tasks/assign/', 'POST', payload);
  showToast("Task successfully assigned to learner!", "success");
  form.reset();
}

// -------------------------------------------------------------
// VIEW 9: ADMINISTRATOR VIEW (FR-1.3, FR-4.8)
// -------------------------------------------------------------
async function loadAdminView(container) {
  const metrics = await api('/admin/metrics/');
  const ledger = await api('/admin/xp_ledger/');

  container.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 26px; font-weight: 700;">System Administrator Portal</h2>
      <p style="color: var(--text-muted); font-size: 14px;">Monitor system health, XP ledger audit trail, and users.</p>
    </div>

    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px;">
      <div class="quest-card" style="text-align: center;">
        <span style="font-size: 12px; color: var(--text-muted);">Total Users</span>
        <h3 style="font-size: 28px; font-weight: 800; color: #fff; margin-top: 4px;">${metrics.total_users}</h3>
      </div>
      <div class="quest-card" style="text-align: center;">
        <span style="font-size: 12px; color: var(--text-muted);">Total Tasks</span>
        <h3 style="font-size: 28px; font-weight: 800; color: var(--purple-light); margin-top: 4px;">${metrics.total_tasks}</h3>
      </div>
      <div class="quest-card" style="text-align: center;">
        <span style="font-size: 12px; color: var(--text-muted);">Focus Hours Logged</span>
        <h3 style="font-size: 28px; font-weight: 800; color: #fb923c; margin-top: 4px;">${metrics.total_focus_hours} h</h3>
      </div>
      <div class="quest-card" style="text-align: center;">
        <span style="font-size: 12px; color: var(--text-muted);">Total XP Awarded</span>
        <h3 style="font-size: 28px; font-weight: 800; color: #34d399; margin-top: 4px;">${metrics.total_xp_awarded}</h3>
      </div>
    </div>

    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 14px; color: #fff;">System XP Audit Trail</h3>
    <div class="quest-card" style="padding: 16px 20px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13.5px; text-align: left;">
        <thead>
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted);">
            <th style="padding: 10px;">ID</th>
            <th style="padding: 10px;">User</th>
            <th style="padding: 10px;">Reason</th>
            <th style="padding: 10px;">Task</th>
            <th style="padding: 10px; text-align: right;">Amount</th>
          </tr>
        </thead>
        <tbody>
          ${ledger.map(e => `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
              <td style="padding: 10px; color: var(--text-dim);">#${e.id}</td>
              <td style="padding: 10px; color: #fff; font-weight: 600;">${escapeHTML(e.user)}</td>
              <td style="padding: 10px;">${escapeHTML(e.reason)}</td>
              <td style="padding: 10px; color: var(--purple-light);">${escapeHTML(e.task || '-')}</td>
              <td style="padding: 10px; text-align: right; color: #34d399; font-weight: 700;">+${e.amount} XP</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// -------------------------------------------------------------
// EVENT LISTENERS & HELPERS
// -------------------------------------------------------------
function setupEventListeners() {
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.trim();
      if (state.currentView === 'tasks') {
        renderActiveView();
      }
    });
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        setView('tasks');
      }
    });
  }
}

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Start application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});
