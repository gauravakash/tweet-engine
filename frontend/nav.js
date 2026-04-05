/**
 * nav.js — shared sidebar, toast system, and API helpers.
 * Included on every page via <script src="nav.js">.
 */

const API = 'http://localhost:8000';

// ── SVG icons ─────────────────────────────────────────────────────────────

const ICONS = {
  dashboard: `<svg viewBox="0 0 16 16" fill="currentColor">
    <rect x="1" y="1" width="6" height="6" rx="1"/>
    <rect x="9" y="1" width="6" height="6" rx="1"/>
    <rect x="1" y="9" width="6" height="6" rx="1"/>
    <rect x="9" y="9" width="6" height="6" rx="1"/>
  </svg>`,
  compose: `<svg viewBox="0 0 16 16" fill="currentColor">
    <path d="M11.5 1.5a1.5 1.5 0 0 1 2.12 2.12L5 12.24l-3 .76.76-3L11.5 1.5z"/>
  </svg>`,
  queue: `<svg viewBox="0 0 16 16" fill="currentColor">
    <rect x="1" y="3" width="14" height="2" rx="1"/>
    <rect x="1" y="7" width="14" height="2" rx="1"/>
    <rect x="1" y="11" width="9"  height="2" rx="1"/>
  </svg>`,
  history: `<svg viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 1a7 7 0 1 0 7 7A7 7 0 0 0 8 1zm.5 7.21V4.5a.5.5 0 0 0-1 0v4a.5.5 0 0 0 .15.35l2.5 2.5a.5.5 0 0 0 .7-.7z"/>
  </svg>`,
  accounts: `<svg viewBox="0 0 16 16" fill="currentColor">
    <circle cx="8" cy="5" r="3"/>
    <path d="M2 14c0-3.31 2.69-6 6-6s6 2.69 6 6H2z"/>
  </svg>`,
  settings: `<svg viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 5.5A2.5 2.5 0 1 0 8 10.5 2.5 2.5 0 0 0 8 5.5zM13.5 7h-.9a4.5 4.5 0 0 0-.45-1.08l.64-.64a.5.5 0 0 0 0-.71l-.86-.86a.5.5 0 0 0-.71 0l-.64.64A4.5 4.5 0 0 0 9 3.9V3a.5.5 0 0 0-.5-.5h-1.2A.5.5 0 0 0 6.8 3v.9a4.5 4.5 0 0 0-1.08.45l-.64-.64a.5.5 0 0 0-.71 0l-.86.86a.5.5 0 0 0 0 .71l.64.64A4.5 4.5 0 0 0 3.7 7H3a.5.5 0 0 0-.5.5v1.2c0 .28.22.5.5.5h.7a4.5 4.5 0 0 0 .45 1.08l-.64.64a.5.5 0 0 0 0 .71l.86.86a.5.5 0 0 0 .71 0l.64-.64c.33.19.7.34 1.08.45V13a.5.5 0 0 0 .5.5h1.2a.5.5 0 0 0 .5-.5v-.7a4.5 4.5 0 0 0 1.08-.45l.64.64a.5.5 0 0 0 .71 0l.86-.86a.5.5 0 0 0 0-.71l-.64-.64A4.5 4.5 0 0 0 12.7 9h.8a.5.5 0 0 0 .5-.5V7.5a.5.5 0 0 0-.5-.5z"/>
  </svg>`,
};

const NAV_ITEMS = [
  { href: 'index.html',    label: 'Dashboard', icon: 'dashboard' },
  { href: 'compose.html',  label: 'Compose',   icon: 'compose'   },
  { href: 'queue.html',    label: 'Queue',     icon: 'queue'     },
  { href: 'history.html',  label: 'History',   icon: 'history'   },
  { href: 'accounts.html', label: 'Accounts',  icon: 'accounts'  },
  { href: 'settings.html', label: 'Settings',  icon: 'settings'  },
];

// ── Sidebar renderer ───────────────────────────────────────────────────────

function renderNav() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  // Detect current page (works for both /index.html and /)
  const page = location.pathname.split('/').pop() || 'index.html';

  sidebar.innerHTML = `
    <div class="sidebar-logo">Tweet<span>Engine</span></div>
    ${NAV_ITEMS.map(item => `
      <a href="${item.href}" class="nav-item ${page === item.href ? 'active' : ''}">
        ${ICONS[item.icon]}
        <span class="nav-label">${item.label}</span>
      </a>
    `).join('')}
  `;
}

// ── Toast system ───────────────────────────────────────────────────────────

const _toastWrap = document.createElement('div');
_toastWrap.className = 'toast-container';
document.addEventListener('DOMContentLoaded', () => document.body.appendChild(_toastWrap));

function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  _toastWrap.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity 0.3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 320);
  }, 3200);
}

// ── API helper ─────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);

  let res;
  try {
    res = await fetch(API + path, opts);
  } catch {
    throw new Error('Cannot reach the server. Is it running on port 8000?');
  }

  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** Returns a coloured badge HTML string for a tone name. */
function toneBadge(tone) {
  if (!tone) return '<span class="badge badge-analytical">—</span>';
  return `<span class="badge badge-${tone.toLowerCase()}">${tone}</span>`;
}

/** Returns a coloured badge HTML string for a status value. */
function statusBadge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

/** Human-readable relative time string (e.g. "3h ago"). */
function relTime(dateStr) {
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
  const diff = Date.now() - d.getTime();
  if (isNaN(diff)) return dateStr;
  if (diff < 60_000)   return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Formatted datetime string for table display. */
function fmtDate(dateStr) {
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
  if (isNaN(d)) return dateStr;
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/** Set button to loading state; returns a restore function. */
function btnLoading(btn, text = 'Loading…') {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> ${text}`;
  return () => { btn.disabled = false; btn.innerHTML = orig; };
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', renderNav);
