/* GTM Shortlist "alive" prototype: shared behaviour. No framework; Lenis is the only dependency. */
(function () {
  const params = new URLSearchParams(location.search);
  const reduced = params.get('motion') === 'reduce' || (params.get('motion') !== 'full' && matchMedia('(prefers-reduced-motion: reduce)').matches);
  if (reduced) document.documentElement.dataset.motion = 'reduce';

  /* ---- Smooth scroll (Alia feel). Native scrolling under reduced motion. ---- */
  let lenis = null;
  const scrollListeners = [];
  if (!reduced && window.Lenis) {
    lenis = new window.Lenis({ autoRaf: true, lerp: 0.1, wheelMultiplier: 1, anchors: { offset: -72 } });
    lenis.on('scroll', () => scrollListeners.forEach((fn) => fn(window.scrollY)));
  } else {
    addEventListener('scroll', () => scrollListeners.forEach((fn) => fn(window.scrollY)), { passive: true });
  }
  addEventListener('resize', () => scrollListeners.forEach((fn) => fn(window.scrollY)));
  const onScroll = (fn) => { scrollListeners.push(fn); fn(window.scrollY); };
  const scrollToY = (y, done) => {
    if (lenis) lenis.scrollTo(y, { duration: 1.1, onComplete: done });
    else { window.scrollTo({ top: y, behavior: 'auto' }); done && done(); }
  };

  /* ---- Word reveal: wrap words, reveal when the heading enters view. ---- */
  function splitWords(el) {
    let i = 0;
    const walk = (node) => {
      [...node.childNodes].forEach((child) => {
        if (child.nodeType === 3) {
          const parts = child.textContent.split(/(\s+)/);
          const frag = document.createDocumentFragment();
          parts.forEach((part) => {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
            const span = document.createElement('span');
            span.className = 'w'; span.style.setProperty('--i', i++); span.textContent = part;
            frag.appendChild(span);
          });
          child.replaceWith(frag);
        } else if (child.nodeType === 1 && child.tagName !== 'BR') walk(child);
      });
    };
    walk(el);
  }
  function setupReveal(root = document) {
    const els = root.querySelectorAll('[data-reveal]');
    els.forEach((el) => { if (!el.dataset.split) { splitWords(el); el.dataset.split = '1'; } });
    if (reduced) { els.forEach((el) => (el.dataset.reveal = 'shown')); return; }
    const io = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.dataset.reveal = 'shown'; io.unobserve(e.target); } }), { threshold: 0.35 });
    els.forEach((el) => { if (el.dataset.reveal !== 'shown') { el.dataset.reveal = 'hidden'; io.observe(el); } });
  }

  /* ---- Blueprint draw-in: stroke-dashoffset per path, pins pop, modules fade. ---- */
  function prepareDraw(svg) {
    svg.querySelectorAll('path, line, polyline, polygon, circle.ln, rect').forEach((el) => {
      try { const len = Math.ceil(el.getTotalLength()) + 2; el.style.setProperty('--len', len); } catch (e) {}
    });
  }
  function setupDraw(root = document) {
    const svgs = root.querySelectorAll('svg.draw');
    svgs.forEach(prepareDraw);
    if (reduced) { svgs.forEach((s) => s.classList.add('drawn')); return; }
    svgs.forEach((s) => s.classList.add('pending'));
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const s = e.target; io.unobserve(s);
      requestAnimationFrame(() => { s.classList.add('drawn'); s.classList.remove('pending'); });
    }), { threshold: 0.25 });
    svgs.forEach((s) => io.observe(s));
  }

  /* ---- Count-up for real counters (event-driven, never timer-invented). ---- */
  function countTo(el, to, ms = 500) {
    const from = +el.textContent || 0;
    if (reduced || from === to) { el.textContent = to; return; }
    const t0 = performance.now();
    const tick = (t) => { const k = Math.min(1, (t - t0) / ms); el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }

  /* ---- Button ripple (Eygentic buttonRipple) ---- */
  document.addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.btn'); if (!b || reduced) return;
    const r = b.getBoundingClientRect(); const s = document.createElement('span');
    s.className = 'ripple'; s.style.left = e.clientX - r.left + 'px'; s.style.top = e.clientY - r.top + 'px';
    b.appendChild(s); setTimeout(() => s.remove(), 650);
  });

  /* ---- Flow lines: S-curves converging on a target, with dots riding them.
     Speed eases toward a target value (about 1 s), like Explee's motion-value tween. ---- */
  class FlowLines {
    constructor(canvas, geometry, opts = {}) {
      this.c = canvas; this.ctx = canvas.getContext('2d'); this.geometry = geometry;
      this.base = opts.base ?? 0.045; this.speed = this.base; this.target = this.base; this.boostUntil = 0;
      this.dotsPerCurve = opts.dotsPerCurve ?? 3; this.onSpeed = opts.onSpeed;
      this.visible = true; this.t0 = performance.now(); this.last = this.t0; this.raf = 0;
      this.resize = this.resize.bind(this); this.frame = this.frame.bind(this);
      new ResizeObserver(this.resize).observe(canvas.parentElement);
      new IntersectionObserver((es) => { this.visible = es[0].isIntersecting; this.kick(); }).observe(canvas);
      document.addEventListener('visibilitychange', () => this.kick());
      this.resize();
    }
    setHover(on) { this.hover = on; this.retarget(); }
    boost(ms = 1200) { this.boostUntil = performance.now() + ms; this.retarget(); clearTimeout(this.bt); this.bt = setTimeout(() => this.retarget(), ms + 20); }
    retarget() { const typing = performance.now() < this.boostUntil; this.target = this.base * (typing ? 24 : this.hover ? 12 : 1); this.kick(); }
    resize() {
      const p = this.c.parentElement.getBoundingClientRect(); const dpr = Math.min(1.5, devicePixelRatio || 1);
      this.w = p.width; this.h = p.height; this.c.width = Math.round(p.width * dpr); this.c.height = Math.round(p.height * dpr);
      this.c.style.width = p.width + 'px'; this.c.style.height = p.height + 'px'; this.dpr = dpr;
      this.curves = this.geometry(this.c.parentElement) || [];
      const dots = [];
      this.curves.forEach((cv, ci) => { for (let k = 0; k < (cv.dots ?? this.dotsPerCurve); k++) dots.push({ ci, t: (k + Math.random()) / (cv.dots ?? this.dotsPerCurve), v: 0.75 + Math.random() * 0.5, hot: cv.hot || Math.random() < 0.22 }); });
      this.dots = dots; this.kick(true);
    }
    kick(force) { if (force || (!this.raf && this.visible && !document.hidden)) { cancelAnimationFrame(this.raf); this.raf = requestAnimationFrame(this.frame); } }
    pt(cv, t) { const u = 1 - t; const [a, b, c, d] = cv.p; return [u * u * u * a[0] + 3 * u * u * t * b[0] + 3 * u * t * t * c[0] + t * t * t * d[0], u * u * u * a[1] + 3 * u * u * t * b[1] + 3 * u * t * t * c[1] + t * t * t * d[1]]; }
    frame(now) {
      this.raf = 0;
      const dt = Math.min(64, now - this.last) / 1000; this.last = now;
      this.speed += (this.target - this.speed) * (1 - Math.exp(-dt * 3.2));
      const ctx = this.ctx; ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); ctx.clearRect(0, 0, this.w, this.h);
      const intro = reduced ? 1 : Math.min(1, (now - this.t0) / 1400);
      this.curves.forEach((cv, i) => {
        const k = reduced ? 1 : Math.max(0, Math.min(1, (intro * 1.6 - i * 0.04)));
        if (k <= 0) return; const e = 1 - Math.pow(1 - k, 3);
        ctx.beginPath(); ctx.lineWidth = cv.w ?? 1; ctx.strokeStyle = cv.color ?? 'rgba(27,27,27,.16)';
        if (cv.dash) ctx.setLineDash(cv.dash); else if (e < 1) ctx.setLineDash([e * 2000, 2000]); else ctx.setLineDash([]);
        const [a, b, c, d] = cv.p; ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(b[0], b[1], c[0], c[1], d[0], d[1]); ctx.stroke();
      });
      ctx.setLineDash([]);
      if (intro > 0.5) this.dots.forEach((dot) => {
        const cv = this.curves[dot.ci]; if (!cv) return;
        if (!reduced) dot.t += this.speed * dot.v * dt * (cv.len ?? 1);
        if (dot.t > 1) { dot.t -= 1; dot.v = 0.75 + Math.random() * 0.5; }
        const [x, y] = this.pt(cv, dot.t); const fade = Math.min(1, dot.t * 8, (1 - dot.t) * 6);
        ctx.globalAlpha = fade * (intro - 0.5) * 2; ctx.fillStyle = dot.hot ? '#d5682f' : 'rgba(27,27,27,.45)';
        const s = dot.hot ? 3.5 : 3; ctx.fillRect(x - s / 2, y - s / 2, s, s);
      });
      ctx.globalAlpha = 1;
      if (this.onSpeed) this.onSpeed(this.speed / this.base, dt);
      const settling = Math.abs(this.target - this.speed) > 0.001 || intro < 1;
      if (!reduced && this.visible && !document.hidden) this.raf = requestAnimationFrame(this.frame);
      else if (settling && !reduced) this.raf = requestAnimationFrame(this.frame);
    }
  }

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  window.proto = { reduced, lenis: () => lenis, onScroll, scrollToY, setupReveal, setupDraw, countTo, FlowLines, clamp };
  addEventListener('DOMContentLoaded', () => { setupReveal(); setupDraw(); });
})();
