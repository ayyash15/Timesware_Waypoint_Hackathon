/* Waypoint UI — shared shell + small interactions (vanilla JS, no build step) */

const WP_ICONS = {
  grid: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>',
  list: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>',
  route: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="3" cy="12.5" r="1.6"/><circle cx="13" cy="3.5" r="1.6"/><path d="M4.4 11.3C7 8.5 6 6 9 5"/></svg>',
  pulse: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 8.5h3l1.5-4 2.5 7 1.5-3h4"/></svg>',
  history: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13 4.5A5.5 5.5 0 103.2 9.5"/><path d="M13 1.5v3.5h-3.5"/></svg>',
  calendar: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="12" height="11" rx="1.5"/><path d="M2 6.5h12M5 1.5v3M11 1.5v3"/></svg>',
  pin: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 14.5S13 9.8 13 6.3A5 5 0 003 6.3C3 9.8 8 14.5 8 14.5z"/><circle cx="8" cy="6.3" r="1.7"/></svg>',
  search: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.3 10.3"/></svg>',
  bell: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M8 2.2a3.6 3.6 0 00-3.6 3.6v2.4L3 10.6h10L11.6 8.2V5.8A3.6 3.6 0 008 2.2z"/><path d="M6.6 12.8a1.4 1.4 0 002.8 0"/></svg>',
  user: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="5.3" r="2.6"/><path d="M2.5 14c0-3 2.5-4.7 5.5-4.7s5.5 1.7 5.5 4.7"/></svg>',
  gear: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4.5h9M11.5 4.5a1.5 1.5 0 103 0 1.5 1.5 0 00-3 0zM14 11.5H5M2.5 11.5a1.5 1.5 0 103 0 1.5 1.5 0 00-3 0z"/></svg>',
  home: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7.5L8 2l6 5.5"/><path d="M3.5 6.5V14h9V6.5"/></svg>'
};
function ic(name) {
  return '<span class="ic-svg" style="display:inline-flex;vertical-align:-2px;">' + (WP_ICONS[name] || "") + '</span>';
}

const WP_NAV = [
  { key: "home", label: "Home", href: "index.html", icon: ic("home") },
  { key: "overview", label: "Overview", href: "dispatcher-overview.html", icon: ic("grid") },
  { key: "orders", label: "Orders", href: "dispatcher-overview.html", icon: ic("list") },
  { key: "planning", label: "Planning", href: "dispatcher-allocation.html", icon: ic("route") },
  { key: "live", label: "Live Operations", href: "live-operations.html", icon: ic("pulse") },
  { key: "deferrals", label: "Deferrals", href: "deferral-summary.html", icon: ic("history") },
  { key: "capacity", label: "Capacity Planning", href: "capacity-planning.html", icon: ic("calendar") }
];

function renderSidebar(activeKey) {
  const items = WP_NAV.map(n => `
    <a class="nav-item ${n.key === activeKey ? "active" : ""}" href="${n.href}">
      <span class="ic">${n.icon}</span><span>${n.label}</span>
    </a>`).join("");
  return `
  <aside class="sidebar">
    <a class="sidebar-brand" href="index.html" style="text-decoration:none;" aria-label="Waypoint Home">
      <div class="mark">W</div>
      <div class="name">Waypoint</div>
    </a>
    <nav class="sidebar-nav">${items}</nav>
    <div class="sidebar-foot">
      <a class="nav-item" href="#"><span class="ic">${ic("gear")}</span><span>Settings</span></a>
      <a class="nav-item" href="#"><span class="ic">${ic("user")}</span><span>Nadeeka R. &mdash; Dispatcher</span></a>
    </div>
  </aside>`;
}

function renderTopbar() {
  return `
  <header class="topbar">
    <div class="topbar-left">
      <span class="chip">${ic("calendar")} ${WP_DATA.today}</span>
      <span class="chip">${ic("pin")} ${WP_DATA.depot} Depot</span>
    </div>
    <div class="topbar-right">
      <div class="search-box">${ic("search")} <span>Search outlet, order, vehicle&hellip;</span></div>
      <button class="btn-icon btn-ghost btn" aria-label="Notifications" style="position:relative;">
        ${ic("bell")}<span style="position:absolute;top:6px;right:6px;width:7px;height:7px;border-radius:50%;background:var(--c-danger);"></span>
      </button>
      <div class="avatar">NR</div>
    </div>
  </header>`;
}

function mountDispatcherShell(activeKey) {
  const root = document.getElementById("app-shell");
  if (!root) return;
  root.insertAdjacentHTML("afterbegin", renderSidebar(activeKey));
  const main = document.createElement("div");
  main.className = "main";
  main.innerHTML = renderTopbar() + '<div class="content" id="content"></div>';
  root.appendChild(main);
}

function toast(msg, variant) {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  const el = document.createElement("div");
  el.className = "toast" + (variant === "success" ? " success" : "");
  el.textContent = msg;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

/* Stagger a subtle rise-in across a container's direct children (KPI rows, cards) */
function staggerIn(selectorOrEl, delayStep) {
  const root = typeof selectorOrEl === "string" ? document.querySelector(selectorOrEl) : selectorOrEl;
  if (!root) return;
  Array.from(root.children).forEach((child, i) => {
    child.style.animation = "none";
    child.style.opacity = "0";
    requestAnimationFrame(() => {
      child.style.animation = `wp-rise 420ms cubic-bezier(0.2,0,0,1) both`;
      child.style.animationDelay = `${i * (delayStep || 60)}ms`;
    });
  });
}

/* Offline/sync simulation used on driver + loader screens */
function simulateOfflineCycle(barId) {
  const bar = document.getElementById(barId);
  if (!bar) return;
  setTimeout(() => {
    bar.textContent = "SYNCING\u2026";
    bar.className = "offline-bar syncing";
    setTimeout(() => {
      bar.textContent = "\u2713 ALL RECORDS SYNCED";
      bar.className = "offline-bar synced";
      setTimeout(() => { bar.style.display = "none"; }, 2200);
    }, 1600);
  }, 2600);
}
