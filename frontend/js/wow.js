/* Waypoint UI — WOW layer interactions. Vanilla JS, no build step, no
   external dependencies. Purely additive: every function is opt-in, called
   explicitly per page after the existing app.js render, so nothing here can
   break a screen that doesn't call it. */

(function () {
  /* ---------- Kinetic count-up on any element with a leading number ---------- */
  function countUp(el, duration) {
    if (!el || el.dataset.wowCounted) return;
    const raw = el.textContent.trim();
    const m = raw.match(/-?\d[\d,]*(\.\d+)?/);
    if (!m) return;
    const numStr = m[0].replace(/,/g, "");
    const target = parseFloat(numStr);
    if (isNaN(target)) return;
    const prefix = raw.slice(0, m.index);
    const suffix = raw.slice(m.index + m[0].length);
    const decimals = (numStr.split(".")[1] || "").length;
    const dur = duration || 900;
    const start = performance.now();
    el.dataset.wowCounted = "1";
    function frame(now) {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = target * eased;
      el.textContent = prefix + val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function countUpAll(selector, duration) {
    document.querySelectorAll(selector).forEach((el, i) => setTimeout(() => countUp(el, duration), i * 50));
  }

  /* ---------- Staggered rise-in reveal for a set of elements ---------- */
  function reveal(selector, step) {
    const els = document.querySelectorAll(selector);
    els.forEach((el, i) => {
      el.classList.add("wow-reveal");
      el.style.transitionDelay = (i * (step || 45)) + "ms";
    });
    requestAnimationFrame(() => requestAnimationFrame(() => {
      els.forEach(el => el.classList.add("wow-in"));
    }));
  }

  /* ---------- Fill progress bars in after mount (uses existing .progress transition) ---------- */
  function fillIn(selector) {
    document.querySelectorAll(selector).forEach(bar => {
      const span = bar.querySelector("span");
      if (!span) return;
      const target = span.style.width;
      span.style.width = "0%";
      requestAnimationFrame(() => requestAnimationFrame(() => { span.style.width = target; }));
    });
  }

  /* ---------- Magnetic hover for CTA buttons ---------- */
  function magnetic(selector, strength) {
    const k = strength || 0.18;
    document.querySelectorAll(selector).forEach(el => {
      el.classList.add("wow-magnetic");
      el.addEventListener("mousemove", e => {
        const r = el.getBoundingClientRect();
        const x = e.clientX - r.left - r.width / 2;
        const y = e.clientY - r.top - r.height / 2;
        el.style.transform = `translate(${x * k}px, ${y * k}px)`;
      });
      el.addEventListener("mouseleave", () => { el.style.transform = ""; });
    });
  }

  /* ---------- 3D tilt for cards ---------- */
  function tilt(selector, max) {
    const m = max || 7;
    document.querySelectorAll(selector).forEach(el => {
      el.addEventListener("mousemove", e => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
        const rx = (py - 0.5) * -m, ry = (px - 0.5) * m;
        el.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-3px)`;
      });
      el.addEventListener("mouseleave", () => { el.style.transform = ""; });
    });
  }

  /* ---------- Hero network canvas (index hub): drifting nodes + connecting edges,
     themed as a delivery network. Pure canvas 2D — no WebGL dependency. ---------- */
  function initNetworkCanvas(id) {
    const canvas = document.getElementById(id);
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");
    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w, h, dpr = Math.min(window.devicePixelRatio || 1, 2);
    let nodes = [];

    function resize() {
      const rect = canvas.getBoundingClientRect();
      w = canvas.width = rect.width * dpr;
      h = canvas.height = rect.height * dpr;
    }
    function seed() {
      const count = w < 700 ? 22 : 36;
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.12 * dpr, vy: (Math.random() - 0.5) * 0.12 * dpr,
        r: (Math.random() * 1.6 + 0.8) * dpr,
        hue: Math.random() > 0.72 ? 36 : (Math.random() > 0.5 ? 200 : 190)
      }));
    }
    function step() {
      ctx.clearRect(0, 0, w, h);
      const linkDist = 150 * dpr;
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;
        for (let j = i + 1; j < nodes.length; j++) {
          const o = nodes[j];
          const dx = n.x - o.x, dy = n.y - o.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < linkDist) {
            ctx.strokeStyle = `hsla(${n.hue}, 70%, 60%, ${0.14 * (1 - d / linkDist)})`;
            ctx.lineWidth = 1 * dpr;
            ctx.beginPath(); ctx.moveTo(n.x, n.y); ctx.lineTo(o.x, o.y); ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        ctx.beginPath();
        ctx.fillStyle = `hsla(${n.hue}, 80%, 62%, 0.85)`;
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!reduceMotion) requestAnimationFrame(step);
    }

    resize(); seed();
    window.addEventListener("resize", () => { resize(); seed(); });
    if (reduceMotion) { step(); } else { requestAnimationFrame(step); }
  }

  window.WOW = { countUp, countUpAll, reveal, fillIn, magnetic, tilt, initNetworkCanvas };
})();
