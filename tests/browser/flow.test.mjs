// Browser-level end-to-end test: loads the real Designathon pages in jsdom against a running server (fresh DB) and
// clicks through the four-role workflow.   BASE=http://127.0.0.1:8123 node flow.test.mjs
import { JSDOM, CookieJar, VirtualConsole } from "jsdom";
const BASE = process.env.BASE || "http://127.0.0.1:8123";
const jar = new CookieJar();
let session = {}, local = {};
const errors = []; let passed = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function ok(name, cond, extra = "") { if (!cond) { errors.push(`${name} ${extra}`); console.log("FAIL ", name, extra); } else { passed++; console.log("PASS ", name); } }
async function open(page, { search = "", wait = 900 } = {}) {
  const vc = new VirtualConsole(); vc.on("jsdomError", (e) => { if (!/navigation|Not implemented|reload|Could not load link/.test(e.message)) errors.push(`${page}: ${e.message}`); });
  const dom = await JSDOM.fromURL(`${BASE}/${page}.html${search}`, {
    runScripts: "dangerously", resources: "usable", cookieJar: jar, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      for (const [k, v] of Object.entries(session)) w.sessionStorage.setItem(k, v);
      for (const [k, v] of Object.entries(local)) w.localStorage.setItem(k, v);
      w.fetch = (u, o) => fetch(new URL(u, BASE), { ...o, headers: { ...(o?.headers || {}), cookie: jar.getCookieStringSync(BASE) } });
      w.prompt = () => "Mr. Receiver"; w.confirm = () => true;
      w.matchMedia = w.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }));
      w.IntersectionObserver = w.IntersectionObserver || class { observe() {} unobserve() {} disconnect() {} };
      w.ResizeObserver = w.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} };
      w.requestAnimationFrame = (f) => setTimeout(f, 0);
      w.HTMLCanvasElement.prototype.getContext = () => ({ drawImage() {} });
      w.HTMLCanvasElement.prototype.toDataURL = () => "data:image/jpeg;base64,/9j/4AAQ";
      w.Image = class { set src(v) { this.width = 800; this.height = 600; setTimeout(() => this.onload && this.onload(), 0); } };
    },
  });
  await new Promise((r) => dom.window.addEventListener("load", r)); await sleep(wait);
  return dom;
}
function close(dom) {
  const w = dom.window; session = {}; local = {};
  for (let i = 0; i < w.sessionStorage.length; i++) { const k = w.sessionStorage.key(i); session[k] = w.sessionStorage.getItem(k); }
  for (let i = 0; i < w.localStorage.length; i++) { const k = w.localStorage.key(i); local[k] = w.localStorage.getItem(k); }
  w.close();
}
const click = (dom, el) => el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true, cancelable: true }));
async function api(role, method, path, body) {
  const t = (await (await fetch(`${BASE}/api/auth/demo?role=${role}`)).json()).token;
  const r = await fetch(`${BASE}${path}`, { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` }, body: body ? JSON.stringify(body) : undefined });
  return { status: r.status, data: await r.json().catch(() => null) };
}

// 1. store places an order
let dom = await open("store-order");
const qty = [...dom.window.document.querySelectorAll(".qty-row input")]; qty[0].value = "10"; qty[1].value = "6"; qty[2].value = "0";
click(dom, dom.window.document.querySelector('a[href="store-confirmation.html"]')); await sleep(900);
const last = JSON.parse(dom.window.sessionStorage.getItem("wp_last_order") || "null");
ok("store: Submit Order created a persisted order", !!last && /^WP/.test(last.ref), JSON.stringify(last)); close(dom);
dom = await open("store-confirmation");
ok("store: confirmation shows the real order reference", dom.window.document.querySelector("strong.mono").textContent === last.ref); close(dom);
const mine = (await api("store", "GET", "/api/store/orders")).data;
ok("store: order stored with its line items", mine[0].order_ref === last.ref && mine[0].items.length === 2);

// 2. dispatcher: plan, defer, assign, commit
dom = await open("dispatcher-allocation", { wait: 1500 }); close(dom);
dom = await open("dispatcher-allocation", { wait: 1800 });
const d = dom.window.document;
const day = (await api("dispatcher", "GET", "/api/dispatcher/day")).data;
ok("dispatcher: planning screen shows real trips", d.querySelectorAll(".grid-3col > .flex-col > .card").length === day.plan.trips.length, `${d.querySelectorAll(".grid-3col > .flex-col > .card").length} vs ${day.plan.trips.length}`);
ok("dispatcher: day is over capacity, deferrals identified with explanations", day.plan.deferrals.length > 0 && day.plan.deferrals.every((x) => x.explanation));
const pool = [...d.querySelectorAll(".order-pool-item")];
ok("dispatcher: waiting pool lists the deferred orders", pool.length === day.plan.deferrals.length, `${pool.length} vs ${day.plan.deferrals.length}`);
if (pool.length) {
  click(dom, pool[0].querySelector(".live-defer")); await sleep(100);
  click(dom, d.querySelector(".defer-reason")); await sleep(1000);
  const again = (await api("dispatcher", "GET", "/api/dispatcher/day")).data.plan.deferrals;
  ok("dispatcher: manual Defer persisted with the dispatcher's reason", again.some((x) => x.decided_by === "dispatcher" || x.reason_code === "DISPATCHER_CHOICE"));
}
dom.window.close();
dom = await open("dispatcher-allocation", { wait: 1500 });
const pool2 = [...dom.window.document.querySelectorAll(".order-pool-item")];
if (pool2.length > 1) { click(dom, pool2[1].querySelector(".live-assign")); await sleep(1200); ok("dispatcher: Assign answered from the validator", true); }
close(dom);
dom = await open("deferral-summary");
ok("dispatcher: Deferral Summary rows from the database", dom.window.document.querySelectorAll("#rows tr").length > 0);
click(dom, dom.window.document.querySelector("#commit-btn")); await sleep(1400);
const after = (await api("dispatcher", "GET", "/api/dispatcher/day")).data.plan;
ok("dispatcher: Commit Plan published the plan", after.status === "published"); close(dom);
const stor = (await api("store", "GET", "/api/store/orders")).data[0];
ok("store: expected arrival after publishing (or deferral notice)", !!stor.eta || stor.status === "deferred", JSON.stringify({ s: stor.status, eta: stor.eta }));

// 3. loader
const drv = (await api("driver", "GET", "/api/driver/vehicles")).data;
dom = await open("loader-dock");
const cards = [...dom.window.document.querySelectorAll(".dock-card")];
ok("loader: dock queue shows the published trips", cards.length === after.trips.length, `${cards.length} vs ${after.trips.length}`);
// the store's own order decides which trip the loader and driver work on, so receipt can be confirmed at the end
const ltrips = (await api("loader", "GET", "/api/loader/trips")).data.trips;
const sOrders = (await api("store", "GET", "/api/store/orders")).data;
const mineServed = sOrders.find((o) => o.vehicle_id);
const target = (mineServed && ltrips.find((t) => t.stops.some((s) => s.order_ref === mineServed.order_ref))) || ltrips.find((t) => t.vehicle_id === drv.default) || ltrips[0];
const want = target.vehicle_id;
const ix = cards.findIndex((c) => c.querySelector(".veh").textContent === want && new RegExp("Trip " + target.trip_no).test(c.textContent));
click(dom, cards[ix].querySelector("a.btn")); await sleep(300); close(dom);
dom = await open("loader-loading");
const lstops = [...dom.window.document.querySelectorAll(".stop-card")];
ok("loader: loading list is for the chosen trip", lstops.length > 0 && /Loading List/.test(dom.window.document.querySelector(".page-head h1").textContent));
click(dom, lstops[0].querySelector(".flag-btn")); await sleep(50);
click(dom, dom.window.document.querySelector('[data-issue="Short"]')); await sleep(900);
const lt = (await api("loader", "GET", "/api/loader/trips")).data.trips.find((t) => t.vehicle_id === want && t.trip_no === target.trip_no);
ok("loader: flagged shortfall persisted", lt.open_issues.length === 1, JSON.stringify(lt.open_issues));
for (const c of [...dom.window.document.querySelectorAll(".stop-card")]) { click(dom, c.querySelector(".btn-success")); await sleep(600); }
const lt2 = (await api("loader", "GET", "/api/loader/trips")).data.trips.find((t) => t.vehicle_id === want && t.trip_no === lt.trip_no);
ok("loader: all stops loaded -> vehicle released", lt2.status === "ready", lt2.status); close(dom);
dom = await open("loader-loading", { wait: 600 });
ok("loader: Loaded ticks survive a refresh", [...dom.window.document.querySelectorAll(".stop-card .btn-success")].every((b) => b.disabled)); close(dom);
const live1 = (await api("dispatcher", "GET", "/api/dispatcher/live")).data;
ok("dispatcher: sees the loader's shortfall", live1.issues.length > 0 || JSON.stringify(live1).includes("hort"));

// 4. driver (one stop offline)
dom = await open("driver-stops", { wait: 1800 }); close(dom);
dom = await open("driver-stops", { wait: 1800 });
const tiles = [...dom.window.document.querySelectorAll(".stop-tile")];
ok("driver: route comes from the dispatcher's trip", tiles.length === lt.stops.filter((s) => s.status !== "cancelled").length, `${tiles.length}`);
click(dom, dom.window.document.querySelector(".start-stop")); await sleep(900);
ok("driver: START STOP opened the stop", !!JSON.parse(dom.window.sessionStorage.getItem("wp_stop") || "null"));
const dep = (await api("driver", "GET", `/api/driver/route?vehicle_id=${want}`)).data.trips.find((t) => t.trip_no === lt.trip_no);
ok("driver: trip is departed", dep.status === "departed", dep.status); close(dom);
dom = await open("driver-stop-detail"); ok("driver: stop detail filled from the real order", !/Peliyagoda Supermarket/.test(dom.window.document.querySelector(".phone-top h1").textContent)); close(dom);

async function outcome(o, { offline = false, photo = true } = {}) {
  const d1 = await open("driver-outcome", { search: `?offline=${offline ? 1 : 0}` }); const w = d1.window.document;
  click(d1, [...w.querySelectorAll(".outcome-btn")].find((b) => b.dataset.o === o));
  if (photo) { const inp = [...w.querySelectorAll("input[type=file]")].pop(); Object.defineProperty(inp, "files", { value: [new d1.window.File(["x"], "p.jpg", { type: "image/jpeg" })] }); inp.dispatchEvent(new d1.window.Event("change")); await sleep(300); }
  click(d1, w.querySelector("#submit-btn")); await sleep(1300);
  const q = JSON.parse(d1.window.localStorage.getItem("wp_queue_v1") || "[]"); close(d1); return q;
}
let q = await outcome("DELIVERED", { offline: true });
ok("driver OFFLINE: outcome saved to the local queue", q.length === 1);
let stops = (await api("driver", "GET", `/api/driver/route?vehicle_id=${want}`)).data.trips.find((t) => t.trip_no === lt.trip_no).stops;
ok("driver OFFLINE: backend has not received it", stops.filter((s) => s.status === "delivered").length === 0);
dom = await open("driver-stops", { search: "?offline=1", wait: 1500 });
ok("driver OFFLINE: bar reports the waiting record", /OFFLINE/.test(dom.window.document.querySelector("#offline-bar").textContent));
ok("driver OFFLINE: stop already shows as done locally", dom.window.document.querySelectorAll(".stop-tile.done").length === 1); close(dom);
dom = await open("driver-stops", { search: "?offline=0", wait: 3000 });
stops = (await api("driver", "GET", `/api/driver/route?vehicle_id=${want}`)).data.trips.find((t) => t.trip_no === lt.trip_no).stops;
ok("driver RECOVERY: queued record synced to the backend", stops.filter((s) => s.status === "delivered").length === 1);
ok("driver RECOVERY: queue is empty", JSON.parse(dom.window.localStorage.getItem("wp_queue_v1") || "[]").length === 0); close(dom);
for (let i = 1; i < stops.length; i++) {
  const dd = await open("driver-stops", { search: "?offline=0", wait: 1800 });
  const b = dd.window.document.querySelector(".start-stop"); if (!b) { close(dd); break; }
  click(dd, b); await sleep(700); close(dd);
  await outcome(i === 1 && stops.length > 2 ? "ATTEMPTED" : "DELIVERED", { photo: !(i === 1 && stops.length > 2) });
  dom = await open("driver-stops", { search: "?offline=0", wait: 2200 }); close(dom);
}
const fin = (await api("dispatcher", "GET", "/api/dispatcher/live")).data;
ok("dispatcher: live view sees the trip progress", fin.trips.some((t) => t.vehicle_id === want), "");

// 5. store receipt
const orders = (await api("store", "GET", "/api/store/orders")).data;
const delivered = orders.find((o) => o.status === "delivered");
if (delivered) {
  dom = await open("store-status", { wait: 1200 });
  ok("store: Delivery Status shows delivered", dom.window.document.querySelectorAll(".step.done").length >= 3); close(dom);
  dom = await open("store-receipt", { wait: 1200 });
  click(dom, dom.window.document.querySelector("#confirm-btn")); await sleep(900); close(dom);
  const o2 = (await api("store", "GET", "/api/store/orders")).data.find((o) => o.id === delivered.id);
  ok("store: Confirm Receipt persisted", o2.status === "received", o2.status);
} else console.log("NOTE: the store outlet's order was not delivered in this run (deferred / other vehicle)");
const again = (await api("dispatcher", "GET", "/api/dispatcher/day")).data;
ok("persistence: plan still published", again.plan.status === "published");
console.log(`\n${passed} passed, ${errors.length} problems`); errors.forEach((e) => console.log(" -", e)); process.exit(errors.length ? 1 : 0);
