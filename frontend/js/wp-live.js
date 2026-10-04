/* Waypoint live wiring — the ONLY frontend addition for the Hackathon.
 *
 * The Designathon pages are unchanged (markup, CSS, layout, navigation). Read screens already get their data from
 * /js/data.js, which the backend now generates from the database. This file connects the buttons that were
 * toast()-only in the prototype to the real API, fills the few hardcoded values, and implements the designed
 * offline experience (local queue -> reconnect -> sync) on the driver screens.
 *
 * There is no login screen in the design (the Home hub is the role picker), so each page signs in as the seeded
 * demo account of its role via GET /api/auth/demo?role=... (disable with DEMO_LOGIN=0 on the server).
 */
(function () {
  "use strict";

  var PAGE = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "");
  var ROLE_OF = {
    "dispatcher-overview": "dispatcher", "dispatcher-allocation": "dispatcher", "live-operations": "dispatcher",
    "deferral-summary": "dispatcher", "capacity-planning": "dispatcher",
    "loader-dock": "loader", "loader-loading": "loader",
    "driver-stops": "driver", "driver-stop-detail": "driver", "driver-outcome": "driver",
    "store-order": "store", "store-confirmation": "store", "store-status": "store", "store-deferral": "store", "store-receipt": "store"
  };
  var ROLE = ROLE_OF[PAGE];
  if (!ROLE) return;

  /* ---------------- helpers ---------------- */
  function wpd() { return typeof WP_DATA !== "undefined" ? WP_DATA : {}; }   // WP_DATA is a top-level const, not a window property
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function say(msg, kind) {
    if (typeof toast === "function") return toast(msg, kind);
    var st = $(".toast-stack"); if (!st) { st = document.createElement("div"); st.className = "toast-stack"; document.body.appendChild(st); }
    var el = document.createElement("div"); el.className = "toast" + (kind === "success" ? " success" : ""); el.textContent = msg; st.appendChild(el);
    setTimeout(function () { el.remove(); }, 3200);
  }
  function later(fn, ms) { setTimeout(fn, ms); }          // the pages' count-up animations finish ~900 ms after load
  function setCookie(k, v) { document.cookie = k + "=" + encodeURIComponent(v) + "; path=/; max-age=86400; SameSite=Lax"; }
  function getCookie(k) { var m = document.cookie.match(new RegExp("(?:^|; )" + k + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : null; }
  function clone(el) { var c = el.cloneNode(true); el.parentNode.replaceChild(c, el); return c; }   // drops the prototype's toast-only listeners
  function hhmm(d) { d = d || new Date(); return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); }
  function ampm(t) { if (!t) return ""; var p = t.split(":"), h = +p[0]; return ((h + 11) % 12 + 1) + ":" + p[1] + " " + (h >= 12 ? "PM" : "AM"); }
  function niceDate(iso) {
    if (!iso) return ""; var d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function errText(r) {
    var d = r && r.data && r.data.detail;
    if (!d) return "Something went wrong (" + (r ? r.status : "offline") + ")";
    if (typeof d === "string") return d;
    if (d.errors) return d.errors.join(" ");
    return JSON.stringify(d);
  }

  /* ---------------- auth + api ---------------- */
  var tokKey = "wp_tok_" + ROLE;
  async function login() {
    var r = await fetch("/api/auth/demo?role=" + ROLE);
    if (!r.ok) throw new Error("Demo sign-in failed (" + r.status + ")");
    var j = await r.json(); sessionStorage.setItem(tokKey, j.token); sessionStorage.setItem("wp_user_" + ROLE, JSON.stringify(j.user));
    return j.token;
  }
  async function api(method, path, body, retried) {
    var tok = sessionStorage.getItem(tokKey);
    try {
      if (!tok) tok = await login();
      var res = await fetch("/api" + path, {
        method: method, headers: { "Content-Type": "application/json", Authorization: "Bearer " + tok },
        body: body === undefined ? undefined : JSON.stringify(body)
      });
      if (res.status === 401 && !retried) { sessionStorage.removeItem(tokKey); return api(method, path, body, true); }
      var data = null; try { data = await res.json(); } catch (e) { /* empty */ }
      return { ok: res.ok, status: res.status, data: data };
    } catch (e) {
      return { ok: false, status: 0, data: null, network: true };
    }
  }

  /* ---------------- DISPATCHER ---------------- */
  async function ensurePlan() {
    var r = await api("GET", "/dispatcher/day");
    if (!r.ok) return null;
    if (!r.data.plan && r.data.orders.length) {
      var run = await api("POST", "/dispatcher/plan/run", {});
      if (run.ok && !sessionStorage.getItem("wp_plan_reload")) { sessionStorage.setItem("wp_plan_reload", "1"); location.reload(); return null; }
      r = await api("GET", "/dispatcher/day");
    }
    sessionStorage.removeItem("wp_plan_reload");
    return r.data;
  }

  function reasonCounts(defs) {
    var c = {}; defs.forEach(function (d) { c[d.constraint || d.reason_code] = (c[d.constraint || d.reason_code] || 0) + 1; });
    return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).map(function (k) { return [k, c[k]]; });
  }

  async function dispatcherAllocation() {
    var day = await ensurePlan(); if (!day || !day.plan) return;
    var plan = day.plan, cap = day.capacity, defs = plan.deferrals, trips = plan.trips, locked = plan.status === "published";
    var reefersUsed = new Set(trips.filter(function (t) { return t.vehicle_temp === "reefer"; }).map(function (t) { return t.vehicle_id; })).size;
    var vansUsed = new Set(trips.filter(function (t) { return t.vehicle_type === "van"; }).map(function (t) { return t.vehicle_id; })).size;

    // ---- summary strip + shortfall banner (hardcoded in the design) ----
    later(function () {
      var vals = $$(".strip-stat .stat-value");
      var nums = [cap.demand_orders, cap.available, reefersUsed + "/" + cap.reefers_available, vansUsed + "/" + cap.vans_available, defs.length];
      vals.forEach(function (el, i) { if (nums[i] !== undefined) el.textContent = nums[i]; });
    }, 1100);
    var banner = $("#shortfall-banner");
    if (banner) {
      if (!defs.length) banner.classList.remove("show");
      var ps = $$("p", banner);
      var top = reasonCounts(defs)[0];
      if (ps[0]) ps[0].textContent = defs.length ? "Today's demand exceeds available capacity: " + defs.length + " of " + cap.demand_orders + " orders cannot be served." : "All confirmed orders fit today's capacity.";
      if (ps[1]) ps[1].innerHTML = "<strong>Binding constraint:</strong> " + (top ? esc(top[0]) + " (" + top[1] + " orders). " : "none. ") +
        cap.in_workshop + " of " + cap.vehicles_total + " vehicles are in the workshop; " + cap.reefers_available + " refrigerated vehicles are available.";
      var sf = $("#sf-stats");
      if (sf) sf.innerHTML =
        '<span class="sf-pill"><b>' + cap.demand_orders + '</b>confirmed orders</span>' +
        '<span class="sf-pill"><b>' + reefersUsed + "/" + cap.reefers_available + '</b>refrigerated used</span>' +
        '<span class="sf-pill"><b>' + vansUsed + "/" + cap.vans_available + '</b>vans used</span>' +
        '<span class="sf-pill" style="color:var(--c-danger);"><b>' + defs.length + '</b>orders deferred</span>';
    }
    var rb = $("#review-btn");
    if (rb) rb.innerHTML = defs.length + " orders will be deferred &middot; Review Deferrals";
    var pill = $(".card-title .badge", $(".grid-3col .card"));
    if (pill) pill.textContent = defs.length;

    // ---- left: waiting pool (deferred orders) ----
    var pool = $("#order-pool");
    pool.innerHTML = defs.length ? defs.map(function (d) {
      return '<div class="order-pool-item risk"><strong>' + esc(d.outlet_id) + '</strong>' +
        '<div class="small muted">' + esc(d.order_ref) + " &middot; " + esc(d.brand) + " &middot; " + esc(d.district) + '</div>' +
        '<div class="small muted" style="margin-top:4px;">' + esc(d.constraint) + '</div>' +
        '<div class="meta"><span class="badge ' + (d.temp === "chilled" ? "badge-chilled" : "badge-neutral") + '">' + (d.temp === "chilled" ? "Chilled" : "Ambient") + '</span>' +
        '<div class="flex gap-2"><button class="btn btn-sm btn-secondary live-defer" data-ref="' + esc(d.order_ref) + '" data-name="' + esc(d.outlet_id) + " &middot; " + esc(d.order_ref) + '"' + (locked ? " disabled" : "") + '>Defer</button>' +
        '<button class="btn btn-sm btn-brand live-assign" data-ref="' + esc(d.order_ref) + '"' + (locked ? " disabled" : "") + '>Assign</button></div></div></div>';
    }).join("") : '<p class="small muted">Every confirmed order is allocated.</p>';

    // ---- centre: vehicle / trip workspace from the real plan ----
    var centre = $(".grid-3col > .flex-col");
    if (centre) centre.innerHTML = trips.map(function (t) {
      var vp = Math.min(100, Math.round(100 * t.volume_m3 / (t.volume_cap_m3 || 1)));
      var tp = Math.min(100, Math.round(100 * t.minutes / (t.budget_min || 1)));
      var kind = (t.vehicle_temp === "reefer" ? "Reefer " : "Dry ") + t.vehicle_type;
      function ok(txt) { return '<div class="check-item ok"><span class="mark">&#10003;</span> ' + txt + '</div>'; }
      return '<div class="card"><div class="card-title">' + esc(t.district) + " " + esc(t.brand) + " &middot; " + esc(t.vehicle_id) + " (" + esc(kind) + ") &middot; Trip " + t.trip_no + '</div>' +
        '<div class="trip-card" style="margin:0; border:none; padding:0;">' +
        t.stops.filter(function (s) { return s.status !== "cancelled"; }).map(function (s) {
          return '<div class="trip-order-row"><span>' + esc(s.outlet_id) + " &middot; " + esc(s.order_ref) + '</span><span class="badge ' + (s.temp === "chilled" ? "badge-chilled" : "badge-neutral") + '">' + (s.temp === "chilled" ? "Chilled" : "Ambient") + '</span></div>';
        }).join("") +
        '<div class="cap-meter-row"><div class="cap-meter"><div class="lbl"><span>Volume</span><span>' + t.volume_m3.toFixed(1) + " / " + t.volume_cap_m3 + ' m&sup3;</span></div><div class="progress"><span style="width:' + vp + '%"></span></div></div>' +
        '<div class="cap-meter"><div class="lbl"><span>Trip time</span><span>' + Math.round(t.minutes) + " / " + t.budget_min + ' min</span></div><div class="progress ' + (tp >= 95 ? "warn" : "") + '"><span style="width:' + tp + '%"></span></div></div></div></div>' +
        '<hr class="divider" style="margin: var(--sp-3) 0;"><div class="check-list">' +
        ok("Capacity valid (volume and weight)") + ok(t.vehicle_temp === "reefer" ? "Temperature compatible" : "Ambient goods only") + ok("Same brand and district") + ok("Trip time within budget") + '</div></div>';
    }).join("");

    // ---- right: constraint & deferral panel with the engine's explanation ----
    var fl = $("#flagged-orders");
    if (fl) fl.innerHTML = defs.length ? defs.slice(0, 8).map(function (d) {
      return '<div class="alert alert-warning" style="margin-bottom:var(--sp-3);"><span class="alert-icon">!</span><div><strong>' + esc(d.outlet_id) + " &middot; " + esc(d.order_ref) + '</strong><p class="small">' + esc(d.explanation) + '</p></div></div>';
    }).join("") + (defs.length > 8 ? '<p class="small muted">+ ' + (defs.length - 8) + " more in the Deferral Summary</p>" : "")
      : '<p class="small muted">No orders fail validation.</p>';

    // ---- actions ----
    var modal = $("#defer-modal"), target = null;
    $$(".live-defer").forEach(function (b) {
      b.addEventListener("click", function () { target = b.dataset.ref; $("#defer-order-name").textContent = b.dataset.name; modal.style.display = "flex"; });
    });
    $$(".defer-reason").forEach(function (old) {
      var b = clone(old);
      b.addEventListener("click", async function () {
        modal.style.display = "none";
        var r = await api("POST", "/dispatcher/plan/" + plan.plan_id + "/defer", { order_ref: target, reason: b.textContent.trim() });
        if (r.ok) { say("Order deferred \u2014 reason recorded: " + b.textContent.trim(), "success"); later(function () { location.reload(); }, 700); }
        else say(errText(r));
      });
    });
    $$(".live-assign").forEach(function (b) {
      b.addEventListener("click", async function () {
        b.disabled = true;
        var r = await api("POST", "/dispatcher/plan/" + plan.plan_id + "/assign-best", { order_ref: b.dataset.ref });
        if (r.ok) { say(b.dataset.ref + " assigned \u2014 plan re-validated", "success"); later(function () { location.reload(); }, 700); }
        else { b.disabled = false; say("Can't assign: " + errText(r)); }
      });
    });
  }

  async function deferralSummary() {
    var day = await ensurePlan(); if (!day || !day.plan) return;
    var plan = day.plan;
    var strong = $(".alert-warning strong");
    if (strong) strong.textContent = plan.deferrals.length + " orders deferred";
    var rep = plan.deferrals.filter(function (d) { return d.deferred_yesterday; }).length;
    var desc = strong && strong.parentNode;
    if (desc) desc.innerHTML = "<strong>" + plan.deferrals.length + " orders deferred</strong> for this run. " + rep + " outlet" + (rep === 1 ? " has" : "s have") + " now been deferred on consecutive runs \u2014 flagged below.";
    var btn = clone($("#commit-btn"));
    if (plan.status === "published") { btn.textContent = "Plan committed"; btn.addEventListener("click", function () { location.href = "live-operations.html"; }); return; }
    btn.addEventListener("click", async function () {
      btn.disabled = true;
      var r = await api("POST", "/dispatcher/plan/" + plan.plan_id + "/publish");
      if (r.ok) { say("Plan committed \u2014 dock queue and driver routes have been generated.", "success"); later(function () { location.href = "live-operations.html"; }, 900); }
      else { btn.disabled = false; say(errText(r)); }
    });
  }

  function dispatcherOverview() {
    var cap = (wpd()).capacity || {};
    later(function () {
      var card = $$("#kpis .kpi-card")[1]; if (!card || cap.demandVolumeM3 === undefined) return;
      $(".stat-value", card).textContent = cap.demandVolumeM3 + " m\u00b3";
      var sub = $(".stat-sub", card); if (sub) sub.textContent = Number(cap.demandWeightKg).toLocaleString("en-US") + " kg";
    }, 1100);
  }

  function liveOperations() {
    var trips = (wpd()).trips || [];
    function n(s) { return trips.filter(function (t) { return t.status === s; }).length; }
    later(function () {
      var tiles = $$("#kpis .kpi-card");
      var vals = [n("In Transit"), trips.filter(function (t) { return /Queued|Loading|Ready/.test(t.status); }).length, n("Completed"), n("Issue Reported")];
      tiles.forEach(function (c, i) { var v = $(".stat-value", c); if (v) v.textContent = vals[i]; });
      var l = $$("#kpis .stat-label")[1]; if (l) l.textContent = "Loading / queued";
    }, 1000);
    if (!trips.length) {
      var rows = $("#rows"); if (rows) rows.innerHTML = '<tr><td colspan="7" class="muted">No vehicles on the road yet \u2014 commit the plan on the Deferrals screen.</td></tr>';
    }
    setInterval(function () { if (!document.hidden) location.reload(); }, 8000);   // shared live view
  }

  /* ---------------- LOADER ---------------- */
  function loaderDock() {
    var q = (wpd()).dockQueue || [];
    if (!q.length) { $("#cards").innerHTML = '<div class="card muted">No published plan yet. The dispatcher commits the plan from the Deferral Summary.</div>'; }
    $$(".dock-card").forEach(function (card, i) {
      var a = $("a.btn", card), d = q[i]; if (!a || !d) return;
      a.addEventListener("click", function () { setCookie("wp_vehicle", d.vehicle); setCookie("wp_trip", d.tripNo); });
    });
    setInterval(function () { if (!document.hidden) location.reload(); }, 10000);
  }

  async function loaderLoading() {
    var D = wpd(), f = D.focus, stops = D.loadingStops || [];
    if (!f) { $("#stops").innerHTML = '<div class="card muted">No published plan yet.</div>'; return; }
    var chip = $(".tb-top .chip"); if (chip) chip.innerHTML = esc(f.vehicle) + " &middot; Trip " + f.tripNo;
    var h1 = $(".page-head h1"); if (h1) h1.innerHTML = "Loading List &middot; " + esc(f.vehicle);
    var desc = $(".page-head .desc"); if (desc) desc.innerHTML = esc(f.trip) + " &middot; departs " + esc(f.departure);
    var released = ["ready", "departed", "completed"].indexOf(f.status) >= 0;
    var cards = $$(".stop-card"), loadedCount = stops.filter(function (s) { return s.loaded; }).length, current = null;

    function markLoaded(btn) { btn.disabled = true; btn.innerHTML = "&#10003; Loaded"; btn.closest(".stop-card").style.opacity = ".7"; }
    async function release(force) {
      var r = await api("POST", "/loader/trips/" + f.tripId + "/ready", { force: !!force });
      if (r.ok) { say("All stops loaded \u2014 vehicle released, driver notified", "success"); return; }
      if (r.status === 409 && r.data && r.data.detail && r.data.detail.needs_force) {
        if (confirm(r.data.detail.errors[0])) return release(true);
        say("Vehicle held \u2014 resolve the flagged issue first");
      } else say(errText(r));
    }
    cards.forEach(function (card, i) {
      var s = stops[i], b = clone($(".btn-success", card));
      if (!s) return;
      if (s.loaded || released) markLoaded(b);
      b.addEventListener("click", async function () {
        b.disabled = true;
        var r = await api("POST", "/loader/stops/" + s.stopId + "/loaded");
        if (!r.ok) { b.disabled = false; say(errText(r)); return; }
        markLoaded(b); say(s.outlet + " marked loaded", "success");
        if (r.data.all_loaded) release(false);
      });
      $(".flag-btn", card).addEventListener("click", function () { current = s; });
    });
    $$("[data-issue]").forEach(function (old) {
      var b = clone(old);
      b.addEventListener("click", async function () {
        $("#flag-modal").style.display = "none";
        if (!current) return;
        var note = prompt("Quantity short / what is wrong? (optional)") || "";
        var r = await api("POST", "/loader/issues", { trip_id: current.tripId, order_id: current.orderId, issue_type: b.dataset.issue.toLowerCase(), note: note });
        if (r.ok) say(b.dataset.issue + " reported for " + current.outlet + " \u2014 Dispatcher and store notified", "success"); else say(errText(r));
      });
    });
  }

  /* ---------------- DRIVER: local queue + offline bar ---------------- */
  var QK = "wp_queue_v1";
  function queue() { try { return JSON.parse(localStorage.getItem(QK) || "[]"); } catch (e) { return []; } }
  function saveQueue(q) { localStorage.setItem(QK, JSON.stringify(q)); }
  function isOffline() {
    var m = location.search.match(/[?&]offline=([01])/); if (m) sessionStorage.setItem("wp_offline", m[1]);
    return sessionStorage.getItem("wp_offline") === "1" || navigator.onLine === false;
  }
  var bar = null, syncing = false;
  function mountBar() {
    var old = $("#offline-bar"); if (!old) return;
    bar = document.createElement("div"); bar.id = "offline-bar"; bar.className = "offline-bar"; bar.style.cursor = "pointer";
    old.parentNode.replaceChild(bar, old);          // the prototype's timed simulation keeps mutating the detached node
    bar.addEventListener("click", function () { if (isOffline() && navigator.onLine !== false) setOffline(false); });
    var av = $(".phone-top .avatar"); if (av) { av.style.cursor = "pointer"; av.title = "Tap to simulate losing signal (demo)"; av.addEventListener("click", function () { setOffline(!isOffline()); }); }
    window.addEventListener("online", renderBar); window.addEventListener("offline", renderBar);
    renderBar();
  }
  function setOffline(on) { sessionStorage.setItem("wp_offline", on ? "1" : "0"); say(on ? "Signal lost (demo) \u2014 work is saved on this phone" : "Back online", on ? undefined : "success"); renderBar(); }
  function renderBar() {
    if (!bar || syncing) return;
    var n = queue().length;
    if (isOffline()) { bar.className = "offline-bar"; bar.style.display = "flex"; bar.textContent = "OFFLINE \u2014 " + (n ? n + " record" + (n > 1 ? "s" : "") + " waiting to sync" : "work is saved on this phone"); }
    else if (n) syncNow();
    else bar.style.display = "none";
  }
  async function syncNow() {
    if (syncing || isOffline()) return;
    var q = queue(); if (!q.length) return;
    syncing = true; bar.style.display = "flex"; bar.className = "offline-bar syncing"; bar.textContent = "SYNCING\u2026";
    var r = await api("POST", "/driver/sync", { events: q });
    syncing = false;
    if (!r.ok) { bar.className = "offline-bar"; bar.textContent = "OFFLINE \u2014 " + q.length + " record(s) waiting to sync"; return; }
    var done = {}; r.data.results.forEach(function (x) { done[x.client_uuid] = x; });
    saveQueue(q.filter(function (e) { return !done[e.client_uuid]; }));
    r.data.results.forEach(function (x) { if (x.result !== "applied" && x.result !== "duplicate") say(x.message, undefined); });
    bar.className = "offline-bar synced"; bar.textContent = "\u2713 ALL RECORDS SYNCED";
    later(function () { bar.style.display = "none"; if (PAGE === "driver-stops") location.reload(); }, 1800);
  }

  async function driverStops() {
    // pick which vehicle/trip this phone shows: the one the loader released, else the account's own
    var v = await api("GET", "/driver/vehicles");
    if (v.ok) {
      var wr = v.data.with_routes || [], act = v.data.active || [], cur = getCookie("wp_vehicle");
      var want = act.indexOf(cur) >= 0 ? cur : act.length ? act[0] : wr.indexOf(cur) >= 0 ? cur : (wr.indexOf(v.data.default) >= 0 ? v.data.default : wr[0]);
      if (want) {
        var rt = await api("GET", "/driver/route?vehicle_id=" + want);
        if (rt.ok && rt.data.trips.length) {
          var ts = rt.data.trips;
          var live = ts.filter(function (t) { return t.status === "ready" || t.status === "departed"; });
          var open = ts.filter(function (t) { return t.stops.some(function (s) { return s.status === "pending"; }); });
          var tn = String((live[0] || open[0] || ts[ts.length - 1]).trip_no);
          localStorage.setItem("wp_route_cache", JSON.stringify(rt.data));
          if (getCookie("wp_vehicle") !== want || getCookie("wp_trip") !== tn) { setCookie("wp_vehicle", want); setCookie("wp_trip", tn); location.reload(); return; }
        }
      }
    }
    var D = wpd(), f = D.focus, wrap = $("#stops");
    var route; try { route = JSON.parse(localStorage.getItem("wp_route_cache") || "null"); } catch (e) { route = null; }
    if (!f) { wrap.innerHTML = '<div class="card muted" style="margin:16px;">No route yet \u2014 waiting for the dispatcher to commit the plan.</div>'; mountBar(); return; }
    var sub = $(".phone-top .small"); if (sub) sub.innerHTML = esc(f.driver.replace(/ \(.*/, "")) + " &middot; " + esc(f.vehicle);
    var h1 = $(".phone-top h1"); if (h1) h1.innerHTML = esc(f.trip);
    var trip = route && route.trips.filter(function (t) { return t.trip_id === f.tripId; })[0];
    var full = {}; if (trip) trip.stops.forEach(function (s) { full[s.stop_id] = s; });
    var local = {}; queue().forEach(function (e) { local[e.stop_id] = e.status; });

    var list = (D.driverStops || []).map(function (s) { return { s: s, done: s.status === "Done" || !!local[s.stopId], localOnly: s.status !== "Done" && !!local[s.stopId] }; });
    var firstOpen = list.findIndex(function (x) { return !x.done; });
    wrap.innerHTML = list.map(function (x, i) {
      var s = x.s, cls = x.done ? "done" : i === firstOpen ? "current" : "upcoming";
      return '<div class="stop-tile ' + cls + ' flex justify-between items-center"><div class="flex gap-3 items-center"><div class="num">' + (x.done ? "&#10003;" : s.seq) + '</div><div>' +
        '<div style="font-weight:700;">' + esc(s.outlet) + '</div><div class="small muted">ETA ' + esc(s.eta) + " &middot; window " + esc(s.window) + '</div></div></div>' +
        (cls === "current" ? '<a class="btn btn-brand start-stop" data-i="' + i + '" href="driver-stop-detail.html">START STOP</a>' : "") +
        (x.done ? '<span class="badge ' + (x.localOnly ? "badge-warning" : "badge-success") + '">' + (x.localOnly ? "Saved offline" : "Delivered") + '</span>' : "") +
        (cls === "upcoming" ? '<span class="badge badge-neutral">Waiting</span>' : "") + '</div>';
    }).join("");
    var done = list.filter(function (x) { return x.done; }).length;
    $("#route-progress-txt").textContent = done + " of " + list.length + " stops";
    $("#route-progress-fill").style.width = Math.round(100 * done / (list.length || 1)) + "%";

    $$(".start-stop").forEach(function (a) {
      a.addEventListener("click", async function () {
        var s = list[+a.dataset.i].s, fs = full[s.stopId] || {};
        sessionStorage.setItem("wp_stop", JSON.stringify({ stopId: s.stopId, tripId: f.tripId, outlet: s.outlet, seq: s.seq, total: list.length, eta: s.eta, window: s.window,
          district: fs.district, dock: fs.dock_type, parking: fs.parking, mall: fs.mall_window, units: fs.units, items: fs.items, temp: fs.temp, order_ref: fs.order_ref }));
        if (f.status === "ready" && !isOffline()) await api("POST", "/driver/trips/" + f.tripId + "/depart");
        else if (f.status === "planned" || f.status === "loading") say("Heads up: the loader has not released this vehicle yet");
      });
    });
    mountBar();
    setInterval(function () { if (!document.hidden && !isOffline() && !queue().length) location.reload(); }, 15000);
  }

  function driverStopDetail() {
    var st; try { st = JSON.parse(sessionStorage.getItem("wp_stop") || "null"); } catch (e) { st = null; }
    mountBar();
    if (!st) return;
    $(".phone-top h1").textContent = st.outlet;
    var sm = $(".phone-top .small.muted"); if (sm) sm.textContent = "Stop " + st.seq + " of " + st.total;
    var rows = $$(".detail-row .v");
    var dock = (st.dock || "").replace("_", " "), items = (st.items || []).filter(function (i) { return i.qty; });
    var vals = [st.outlet + (st.district ? ", " + st.district : ""), String(st.window || "").replace("-", " \u2013 "), dock.charAt(0).toUpperCase() + dock.slice(1),
      st.parking === "van_only" ? "Van only" : st.parking === "mall_dock" ? "Mall dock" : "Truck bay, no constraint", st.mall || "\u2014",
      (st.units || "") + " units" + (st.temp === "chilled" ? " \u00b7 Chilled" : "") + (items.length ? " \u00b7 " + items.map(function (i) { return i.qty + " " + i.name; }).join(", ") : "")];
    rows.forEach(function (el, i) { if (vals[i] !== undefined) el.textContent = vals[i]; });
    var al = $(".alert-warning");
    if (al) { var b = $("strong", al), p = $("p", al); if (b) b.textContent = dock ? dock.charAt(0).toUpperCase() + dock.slice(1) + " access" : "Access"; if (p) p.textContent = st.mall ? "Mall delivery window " + st.mall + ". Use the shared mall bay." : st.parking === "van_only" ? "Van-only outlet." : "Unload as per the dock type above."; }
  }

  function readPhoto(file) {
    return new Promise(function (resolve) {
      var fr = new FileReader();
      fr.onload = function () {
        var img = new Image();
        img.onload = function () {
          var max = 900, k = Math.min(1, max / Math.max(img.width, img.height)), c = document.createElement("canvas");
          c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL("image/jpeg", 0.6));
        };
        img.onerror = function () { resolve(fr.result); };
        img.src = fr.result;
      };
      fr.readAsDataURL(file);
    });
  }

  function driverOutcome() {
    var st; try { st = JSON.parse(sessionStorage.getItem("wp_stop") || "null"); } catch (e) { st = null; }
    mountBar();
    if (!st) { say("Pick a stop first"); later(function () { location.href = "driver-stops.html"; }, 800); return; }
    var back = $(".phone-top a.small"); if (back) back.innerHTML = "&larr; " + esc(st.outlet);
    var boxes = $$(".pod-box"), photo = null, signer = null;
    var file = document.createElement("input"); file.type = "file"; file.accept = "image/*"; file.setAttribute("capture", "environment"); file.style.display = "none"; document.body.appendChild(file);
    boxes[0].addEventListener("click", function () { file.click(); });
    file.addEventListener("change", async function () {
      if (!file.files || !file.files[0]) return;
      photo = await readPhoto(file.files[0]);
      boxes[0].innerHTML = '<img src="' + photo + '" alt="Proof of delivery" style="max-height:90px;border-radius:8px;"><br><strong>Photo captured &#10003;</strong>';
    });
    boxes[1].addEventListener("click", function () {
      var n = prompt("Receiver's name (signature)"); if (!n) return; signer = n.trim();
      boxes[1].innerHTML = "<strong>Signed by " + esc(signer) + " &#10003;</strong>";
    });
    var btn = clone($("#submit-btn")); btn.disabled = true;
    $$(".outcome-btn").forEach(function (b) { b.addEventListener("click", function () { btn.disabled = false; btn.textContent = b.dataset.o === "DELIVERED" ? "Confirm Delivery" : "Submit Outcome"; }); });
    btn.addEventListener("click", async function () {
      var sel = $(".outcome-btn.selected"); if (!sel) return;
      var o = sel.dataset.o, status = o === "DELIVERED" ? "delivered" : o === "ATTEMPTED" ? "failed" : "partial", note = "";
      if (status !== "failed" && !photo) { say("Add a proof-of-delivery photo first"); return; }
      if (status !== "delivered") {
        note = (prompt(o === "ATTEMPTED" ? "Why could the delivery not be completed?" : "Describe the issue at the outlet") || "").trim();
        if (note.length < 3) { say("A short note is required"); return; }
        note = (o === "ATTEMPTED" ? "Attempted: " : "Issue: ") + note;
      }
      if (signer) note = (note ? note + ". " : "") + "Received by " + signer;
      var ev = { client_uuid: "dev-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8), stop_id: st.stopId, status: status,
        time_in: hhmm(), time_out: hhmm(), note: note || null, pod_photo: photo, recorded_at: new Date().toISOString() };
      var q = queue(); q.push(ev); saveQueue(q);          // always written locally first
      if (isOffline()) say("Outcome recorded \u2014 saved offline, will sync when connected", "success");
      else { say("Outcome recorded", "success"); }
      btn.disabled = true;
      later(function () { location.href = "driver-stops.html"; }, 900);
    });
  }

  /* ---------------- STORE MANAGER ---------------- */
  var outlet = null;
  async function storeHeader() {
    var r = await api("GET", "/store/outlet"); if (!r.ok) return;
    outlet = r.data;
    var u = {}; try { u = JSON.parse(sessionStorage.getItem("wp_user_store") || "{}"); } catch (e) { /* empty */ }
    var chip = $(".sm-top .chip");
    if (chip && !(PAGE === "store-deferral" && !window.__wpDeferred)) chip.innerHTML = esc((u.name || "Store").replace(/ \(.*/, "")) + " &middot; " + esc(outlet.outlet_id) + " &middot; " + esc(outlet.district);
  }
  var statusNames = { confirmed: "Awaiting dispatch planning", planned: "Planned", loaded: "Loaded", in_transit: "In transit", delivered: "Delivered", received: "Receipt confirmed", issue: "Issue reported", deferred: "Deferred", failed: "Delivery failed" };

  async function storeOrder() {
    await storeHeader();
    var desc = $(".page-head .desc"); if (desc && outlet) desc.textContent = "For delivery on " + niceDate(outlet.demo_date);
    var sel = $("select.select"); if (sel && outlet) { sel.value = outlet.brand; sel.disabled = true; }
    var link = $('a[href="store-confirmation.html"]');
    link.addEventListener("click", async function (e) {
      e.preventDefault();
      var rows = $$(".qty-row"), items = [], units = 0;
      rows.forEach(function (r) { var q = parseInt($("input", r).value, 10) || 0; if (q > 0) { items.push({ name: $("span", r).textContent.trim(), qty: q }); units += q; } });
      var chilled = $$('input[name="ttype"]')[1].checked;
      if (!units) { say("Add at least one item"); return; }
      link.style.pointerEvents = "none";
      var r = await api("POST", "/store/orders", { temp_requirement: chilled ? "chilled" : "ambient", order_units: units, items: items });
      link.style.pointerEvents = "";
      if (!r.ok) { say(errText(r)); return; }
      sessionStorage.setItem("wp_last_order", JSON.stringify({ ref: r.data.order_ref, date: r.data.delivery_date, message: r.data.message, after: r.data.after_cutoff, at: hhmm() }));
      location.href = "store-confirmation.html";
    });
  }

  async function storeConfirmation() {
    storeHeader();
    var o; try { o = JSON.parse(sessionStorage.getItem("wp_last_order") || "null"); } catch (e) { o = null; }
    if (!o) return;
    var rows = $$(".card .flex");
    $("strong.mono").textContent = o.ref;
    if (rows[1]) $("strong", rows[1]).textContent = ampm(o.at);
    var badge = $(".card .badge"); if (badge) badge.textContent = o.after ? "Joins the next run" : "Awaiting dispatch planning";
    var p = $("p.muted.small"); if (p) p.textContent = o.message;
  }

  var lastStoreOrders = [];
  async function loadOrders() { var r = await api("GET", "/store/orders"); if (r.ok) lastStoreOrders = r.data; return lastStoreOrders; }

  async function storeStatus() {
    await storeHeader();
    async function fill() {
      var os = await loadOrders(), ref = null; try { ref = (JSON.parse(sessionStorage.getItem("wp_last_order") || "null") || {}).ref; } catch (e) { /* empty */ }
      var o = os.filter(function (x) { return x.order_ref === ref; })[0] || os[0]; if (!o) return;
      $(".page-head .desc").innerHTML = "Order " + esc(o.order_ref) + " &middot; for " + esc(niceDate(o.delivery_date)) + (o.vehicle_id ? " &middot; on " + esc(o.vehicle_id) : "") + " &middot; " + esc(statusNames[o.status] || o.status);
      var eta = $(".eta-big"), lbl = $(".stat-label", eta.parentNode);
      eta.textContent = o.eta ? ampm(o.eta) : o.status === "deferred" ? "Deferred" : "Awaiting plan";
      lbl.textContent = o.status === "delivered" || o.status === "received" ? "Delivered at" : "Arriving approximately";
      if (o.status === "delivered" || o.status === "received") eta.textContent = ampm(o.delivered_at) || "Delivered";
      var cur = { confirmed: -1, planned: 0, loaded: 0, in_transit: 1, delivered: 3, received: 3, issue: 3 }[o.status];
      $$(".step").forEach(function (s, i) { s.className = "step" + (cur === undefined || cur < 0 ? "" : i < cur || (i === cur && cur === 3) ? " done" : i === cur ? " active" : ""); });
      var cta = $('a[href="store-receipt.html"]'), ex = $('a[href="store-deferral.html"]');
      if (cta) { var ready = o.status === "delivered"; cta.textContent = o.status === "received" ? "Receipt confirmed" : ready ? "Confirm Receipt" : "Confirm Receipt (when it arrives)"; cta.style.opacity = ready ? "1" : ".6"; }
      var anyDef = os.some(function (x) { return x.status === "deferred"; });
      if (ex) { ex.innerHTML = anyDef ? "See why an order was deferred &rarr;" : "See a deferred-order example &rarr;"; }
    }
    fill(); setInterval(fill, 6000);
  }

  async function storeDeferral() {
    var os = await loadOrders(), d = os.filter(function (x) { return x.status === "deferred" && x.deferral; })[0];
    if (!d) return;                          // no real deferral: the design's own example stays
    window.__wpDeferred = true; storeHeader();
    var strongs = $$(".card strong");
    $("p", $(".alert-danger")).textContent = "Your order for " + niceDate(d.delivery_date) + " could not be scheduled.";
    if (strongs[0]) strongs[0].textContent = d.deferral.reason;
    if (strongs[1]) strongs[1].textContent = d.deferral.rescheduled_for ? niceDate(d.deferral.rescheduled_for) : "Next run";
    if (strongs[2]) strongs[2].textContent = d.order_ref;
    var p = $("p.small.muted"); if (p) p.textContent = "This wasn't a decision about your outlet specifically \u2014 orders across the network were prioritised by delivery window, outlets already skipped, and days since last served. Your order is first in line on the next run.";
  }

  async function storeReceipt() {
    await storeHeader();
    var os = await loadOrders();
    var o = os.filter(function (x) { return x.status === "delivered"; })[0] || os.filter(function (x) { return x.status === "received" || x.status === "issue"; })[0];
    var confirmBtn = clone($("#confirm-btn"));
    if (o) {
      $(".page-head .desc").innerHTML = "Order " + esc(o.order_ref) + " &middot; delivered " + esc(ampm(o.delivered_at) || "today");
      var tbl = $(".card .compare-head").parentNode;
      $$(".compare-row:not(.compare-head)", tbl).forEach(function (r) { r.remove(); });
      o.items.forEach(function (it) { tbl.insertAdjacentHTML("beforeend", '<div class="compare-row"><span>' + esc(it.name) + "</span><span>" + it.qty + "</span><span>" + it.qty + "</span></div>"); });
    }
    var radios = $$('input[name="issue"]'), names = ["Missing item", "Short quantity", "Damaged item", "Wrong item"];
    $$("#issue-panel label.chip").forEach(function (l, i) { l.lastChild.textContent = names[i]; });
    confirmBtn.addEventListener("click", async function () {
      if (!o) { say("Nothing delivered yet \u2014 you can confirm once the driver records the delivery"); return; }
      var r = await api("POST", "/store/orders/" + o.id + "/receipt", { status: "confirmed" });
      if (r.ok) { say("Receipt confirmed", "success"); later(function () { location.href = "store-status.html"; }, 900); } else say(errText(r));
    });
    var submit = clone($("#issue-panel .btn-brand"));
    submit.addEventListener("click", async function () {
      if (!o) { say("Nothing delivered yet"); return; }
      var i = radios.findIndex(function (r) { return r.checked; });
      var r = await api("POST", "/store/orders/" + o.id + "/receipt", { status: "issue", note: names[i < 0 ? 1 : i] });
      if (r.ok) { say("Discrepancy reported to dispatcher", "success"); later(function () { location.href = "store-status.html"; }, 900); } else say(errText(r));
    });
  }

  /* ---------------- boot ---------------- */
  var routes = {
    "dispatcher-allocation": dispatcherAllocation, "deferral-summary": deferralSummary, "dispatcher-overview": dispatcherOverview,
    "live-operations": liveOperations, "loader-dock": loaderDock, "loader-loading": loaderLoading,
    "driver-stops": driverStops, "driver-stop-detail": driverStopDetail, "driver-outcome": driverOutcome,
    "store-order": storeOrder, "store-confirmation": storeConfirmation, "store-status": storeStatus, "store-deferral": storeDeferral, "store-receipt": storeReceipt
  };
  function boot() {
    var fn = routes[PAGE]; if (!fn) return;
    Promise.resolve().then(fn).catch(function (e) { console.error("[wp-live]", e); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
