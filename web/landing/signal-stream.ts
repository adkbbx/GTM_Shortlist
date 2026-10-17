import { exampleMark, exampleShortlist } from './landing-data';

/* The landing hero's stream. 21 evenly spaced lanes leave the company card, spread across the web and narrow through
   three checks (offer, target, evidence) into the example shortlist. Each check is a wall with one opening exactly as
   wide as the lanes it keeps. Hover and focus speed the stream up; typing pushes harder. Everything shown is a labelled
   synthetic example: the counts are dots crossing the checks, not product metrics. */

export type StreamElements = {
  instrument: HTMLElement; canvas: HTMLCanvasElement; cardIn: HTMLElement; cardOut: HTMLElement; stream: HTMLElement;
  gates: HTMLElement[]; gateTops: HTMLElement[]; gateBottoms: HTMLElement[]; kept: HTMLElement[]; checked: HTMLElement[];
  count: HTMLElement; rows: HTMLElement; portOut: HTMLElement;
};

const N = 21, HALF = (N - 1) / 2, LANES = Array.from({ length: N }, (_, i) => i - HALF);
const KEEP = [HALF, 5, 2, 1], SQUEEZE = [1, 0.8, 0.66];
const DOT: Array<[number, number, number, number]> = [[27, 27, 27, 0.5], [27, 27, 27, 0.72], [180, 80, 28, 0.9], [213, 104, 47, 1]];
const TAU = Math.PI * 2;
// An example shortlist stays shortlist-sized: fewer passing dots are counted as it nears this many companies.
const SHORTLIST_SIZE = 60;
const endsAt = (s: number) => { const m = Math.abs(s); return m > KEEP[1] ? 0 : m > KEEP[2] ? 1 : m > KEEP[3] ? 2 : 3; };
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
const smoother = (t: number) => { t = clamp01(t); return t * t * t * (t * (t * 6 - 15) + 10); };
const rgba = (c: number[], a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const ICON = {
  ok: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m4 8 3 3 5-6"/></svg>',
  you: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 8h8M8 4v8"/></svg>',
};

type Dot = { s: number; a: number; v: number; k: number; end: number; fade: number; counted: boolean; dead?: boolean };

export class SignalStream {
  private ctx: CanvasRenderingContext2D;
  private cache: HTMLCanvasElement | null = null;
  private U = 1; private dpr = 1; private lw = 1; private vertical = false;
  private a0 = 0; private a1 = 1; private c0 = 0; private sp = 10; private fanEnd = 0;
  private G = [0, 0, 0]; private trEnd = [0, 0]; private spans: number[][] = [];
  private dots: Dot[] = []; private glow = [0, 0, 0];
  private speed = 1; private hover = false; private boostUntil = 0; private spawnAcc = 0; private arrivals = 0; private lastRow = 0; private tallyAt = 0;
  private last = 0; private t0 = 0; private visible = true; private nameIndex = 0; private rate = 16; private base = 120; private raf = 0;
  // Seeded so the example reads as a run already under way: 21 lanes keep 11, then 5, then 3.
  private checked = [148, 78, 36]; private keptCount = [78, 36, 22];
  private observers: Array<{ disconnect(): void }> = [];
  private onVisibility = () => this.resume();

  constructor(private el: StreamElements, private reduced: boolean, private verticalQuery: MediaQueryList) {
    const ctx = el.canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas is unavailable');
    this.ctx = ctx;
    this.layout(); this.seed();
    for (let i = 0; i < 6; i++) this.addRow(false);
    this.paintTallies(true);
    this.t0 = this.last = performance.now();
    const resize = new ResizeObserver(() => { const was = this.a1 - this.a0; this.layout(); if (Math.abs(this.a1 - this.a0 - was) > 40) { this.dots = []; this.seed(); } if (this.reduced) this.frame(performance.now()); });
    resize.observe(el.instrument);
    const view = new IntersectionObserver(entries => { const was = this.visible; this.visible = entries[0].isIntersecting; if (this.visible && !was) this.resume(); });
    view.observe(el.instrument);
    this.observers.push(resize, view);
    document.addEventListener('visibilitychange', this.onVisibility);
    if (reduced) this.frame(this.t0); else this.raf = requestAnimationFrame(this.frame);
  }

  destroy() { cancelAnimationFrame(this.raf); this.raf = 0; this.observers.forEach(o => o.disconnect()); document.removeEventListener('visibilitychange', this.onVisibility); }
  setHover(on: boolean) { this.hover = on; }
  boost(ms: number) { this.boostUntil = performance.now() + ms; }
  burst() { this.boost(1600); this.glow = [1, 1, 1]; }

  private resume() { if (this.reduced || this.raf || !this.visible || document.hidden) return; this.last = performance.now(); this.raf = requestAnimationFrame(this.frame); }

  // offset of lane s from the centre line at distance a along the run
  private offAt(s: number, a: number) {
    const { sp, G, trEnd, U } = this;
    if (a <= this.fanEnd) return s * sp * smoother((a - this.a0) / (this.fanEnd - this.a0));
    for (let k = 0; k < 2; k++) {
      const t1 = G[k] + 4 * U;
      if (a <= t1) return s * sp * SQUEEZE[k];
      if (a <= trEnd[k]) return s * sp * lerp(SQUEEZE[k], SQUEEZE[k + 1], smoother((a - t1) / (trEnd[k] - t1)));
    }
    const t1 = G[2] + 4 * U;
    if (a <= t1) return s * sp * SQUEEZE[2];
    return s * sp * SQUEEZE[2] * (1 - smoother((a - t1) / (this.a1 - t1)));
  }
  private at(a: number, o: number): [number, number] { return this.vertical ? [this.c0 + o, a] : [a, this.c0 + o]; }
  // keep straight runs on the pixel grid so hairlines stay sharp
  private snap(v: number, w: number) { const d = this.dpr; return Math.round(w * d) % 2 ? (Math.floor(v * d) + 0.5) / d : Math.round(v * d) / d; }

  private layout() {
    const { el } = this;
    this.U = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
    this.dpr = Math.min(2, window.devicePixelRatio || 1); this.lw = Math.max(1, Math.round(this.U));
    this.vertical = this.verticalQuery.matches;
    const ib = el.instrument.getBoundingClientRect();
    el.canvas.width = Math.round(ib.width * this.dpr); el.canvas.height = Math.round(ib.height * this.dpr);
    el.canvas.style.width = `${ib.width}px`; el.canvas.style.height = `${ib.height}px`;
    const rel = (node: HTMLElement) => { const b = node.getBoundingClientRect(); return { l: b.left - ib.left, r: b.right - ib.left, t: b.top - ib.top, b: b.bottom - ib.top, w: b.width, h: b.height }; };
    const ci = rel(el.cardIn), co = rel(el.cardOut), st = rel(el.stream), U = this.U;
    const fractions = el.gates.map(g => parseFloat(getComputedStyle(g).getPropertyValue('--g')) || 0.5);
    if (!this.vertical) {
      this.a0 = ci.r; this.a1 = co.l; this.c0 = st.t + st.h / 2;
      this.G = fractions.map(x => Math.round(st.l + x * st.w));
      const top = Math.max(...el.gateTops.map(e => rel(e).b)) + 14 * U, bottom = Math.min(...el.gateBottoms.map(e => rel(e).t)) - 14 * U;
      this.sp = Math.max(24, Math.min(this.c0 - top, bottom - this.c0)) / HALF;
      this.spans = el.gateTops.map((e, k) => [rel(e).b + 8 * U, rel(el.gateBottoms[k]).t - 8 * U]);
      this.rate = 18 * Math.min(1.4, Math.max(0.7, (this.a1 - this.a0) / (680 * U))); this.base = 120;
    } else {
      this.a0 = ci.b; this.a1 = co.t; this.c0 = st.l + st.w / 2;
      this.G = fractions.map(x => Math.round(st.t + x * st.h));
      this.sp = Math.min(st.w * 0.24, 8 * 16 * U) / HALF;
      this.spans = this.G.map(() => [st.l, st.r]);
      this.rate = 12; this.base = 85;
    }
    this.fanEnd = this.a0 + (this.vertical ? 0.94 : 0.8) * (this.G[0] - this.a0);
    this.trEnd = [0, 1].map(k => this.G[k] + 4 * U + Math.min(70 * U, 0.5 * (this.G[k + 1] - this.G[k])));
    this.buildCache();
  }

  private trace(c: CanvasRenderingContext2D, s: number, from: number, to: number) {
    for (let a = from, i = 0; ; a = Math.min(to, a + 2), i++) {
      const o = this.offAt(s, a), flat = Math.abs(this.offAt(s, a + 1.5) - o) < 0.01 && Math.abs(this.offAt(s, a - 1.5) - o) < 0.01;
      const cr = flat ? this.snap(this.c0 + o, this.lw) : this.c0 + o;
      if (this.vertical) { if (i) c.lineTo(cr, a); else c.moveTo(cr, a); } else if (i) c.lineTo(a, cr); else c.moveTo(a, cr);
      if (a >= to) break;
    }
  }
  private seg(c: CanvasRenderingContext2D, a: number, from: number, to: number) {
    c.beginPath();
    if (this.vertical) { c.moveTo(from, a); c.lineTo(to, a); } else { c.moveTo(a, from); c.lineTo(a, to); }
    c.stroke();
  }
  private buildCache() {
    const cache = document.createElement('canvas'); cache.width = this.el.canvas.width; cache.height = this.el.canvas.height;
    const c = cache.getContext('2d'); if (!c) return;
    const { G, a0, a1, c0, sp, U, lw } = this;
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); c.lineJoin = 'round'; c.lineWidth = lw;
    const gradient = (from: number, to: number, stops: Array<[number, string]>) => {
      const g = this.vertical ? c.createLinearGradient(0, from, 0, to) : c.createLinearGradient(from, 0, to, 0);
      stops.forEach(([offset, colour]) => g.addColorStop(offset, colour)); return g;
    };
    const ends = [G[0], G[1], G[2], a1];
    const styles = [gradient(a0, G[0], [[0, 'rgba(213,104,47,.55)'], [0.3, 'rgba(27,27,27,.13)'], [1, 'rgba(27,27,27,.13)']]), 'rgba(27,27,27,.2)', 'rgba(27,27,27,.3)',
      gradient(G[2], a1, [[0, 'rgba(213,104,47,.5)'], [1, 'rgba(213,104,47,.85)']])];
    for (const s of LANES) for (let k = 0; k <= endsAt(s); k++) { c.strokeStyle = styles[k]; c.beginPath(); this.trace(c, s, k ? ends[k - 1] : a0, ends[k]); c.stroke(); }
    G.forEach((g, k) => {
      const open = (KEEP[k + 1] + 0.5) * sp * SQUEEZE[k], x = this.snap(g, lw);
      c.lineWidth = lw; c.strokeStyle = 'rgba(27,27,27,.55)'; this.seg(c, x, this.spans[k][0], c0 - open); this.seg(c, x, c0 + open, this.spans[k][1]);
      c.lineWidth = 3 * U; c.strokeStyle = '#d5682f'; this.seg(c, g, c0 - open, c0 + open);
    });
    this.cache = cache;
  }

  private spawn(a = this.a0) {
    const s = LANES[(Math.random() * N) | 0], counted = Math.random() < Math.max(0, 1 - this.keptCount[2] / SHORTLIST_SIZE);
    this.dots.push({ s, a, v: 0.85 + Math.random() * 0.3, k: 0, end: endsAt(s), fade: 0, counted });
  }
  private seed() {
    const n = Math.round(this.rate * (this.a1 - this.a0) / (this.base * this.U));
    for (let i = 0; i < n; i++) {
      this.spawn(this.a0 + Math.random() * (this.a1 - this.a0));
      const d = this.dots[this.dots.length - 1];
      while (d.k < 3 && d.a >= this.G[d.k]) { if (d.end === d.k) { d.dead = true; break; } d.k++; }
    }
    this.dots = this.dots.filter(d => !d.dead);
  }
  private addRow(animate: boolean) {
    const fits = Math.random() < 0.8, company = exampleShortlist[this.nameIndex++ % exampleShortlist.length], sources = 2 + ((Math.random() * 4) | 0);
    const li = document.createElement('li'); if (animate && !this.reduced) li.className = 'new';
    li.innerHTML = `<span class="pl-logo">${exampleMark(company.domain)}</span><span class="pl-dom"><b>${company.name}</b><span>${fits ? `${sources} sources · fits your target` : 'Fits · budget owner unknown'}</span></span><span class="pl-mark ${fits ? 'ok' : 'you'}" role="img" aria-label="${fits ? 'Fits' : 'Needs a call'}">${fits ? ICON.ok : ICON.you}</span>`;
    this.el.rows.prepend(li); while (this.el.rows.children.length > 8) this.el.rows.lastChild?.remove();
    if (animate && !this.reduced) { const p = this.el.portOut; p.classList.remove('ping'); void p.offsetWidth; p.classList.add('ping'); }
  }
  private paintTallies(force = false) {
    const now = performance.now(); if (!force && now - this.tallyAt < 140) return; this.tallyAt = now;
    for (let k = 0; k < 3; k++) { this.el.checked[k].textContent = this.checked[k].toLocaleString('en-US'); this.el.kept[k].textContent = this.keptCount[k].toLocaleString('en-US'); }
    this.el.count.textContent = this.keptCount[2].toLocaleString('en-US');
  }
  private drawDot(d: Dot, alpha: number) {
    const { ctx, U } = this;
    const [x, y] = this.at(d.a, this.offAt(d.s, d.a)), col = d.k === 0 && d.a - this.a0 < 50 * U ? [213, 104, 47, 0.9] : DOT[d.k];
    const ta = Math.max(this.a0, d.a - (d.k === 3 ? 26 : 16) * U), [tx, ty] = this.at(ta, this.offAt(d.s, ta));
    const g = ctx.createLinearGradient(tx, ty, x, y); g.addColorStop(0, rgba(col, 0)); g.addColorStop(1, rgba(col, col[3] * 0.7 * alpha));
    ctx.strokeStyle = g; ctx.lineWidth = (d.k === 3 ? 2 : 1.5) * U; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
    ctx.fillStyle = rgba(col, col[3] * alpha); ctx.beginPath(); ctx.arc(x, y, (d.k === 3 ? 2.4 : 1.8) * U, 0, TAU); ctx.fill();
  }

  private frame = (now: number) => {
    this.raf = 0;
    const { ctx, el, U, G, reduced } = this;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now;
    const intro = reduced ? 1 : clamp01((now - this.t0) / 1500);
    const target = now < this.boostUntil ? 4.5 : this.hover ? 2 : 1;
    this.speed += (target - this.speed) * (1 - Math.exp(-dt * 3));
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, el.canvas.width, el.canvas.height);
    const reach = lerp(this.a0, this.a1, smoother(intro));
    ctx.save();
    if (intro < 1) { ctx.beginPath(); if (this.vertical) ctx.rect(0, 0, el.canvas.width, reach * this.dpr); else ctx.rect(0, 0, reach * this.dpr, el.canvas.height); ctx.clip(); }
    if (this.cache) ctx.drawImage(this.cache, 0, 0);
    ctx.restore();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); ctx.lineCap = 'round';
    // openings glow briefly as companies pass a check
    G.forEach((g, k) => {
      this.glow[k] = Math.max(0, this.glow[k] - dt * 1.6); if (this.glow[k] < 0.02 || g > reach) return;
      const open = (KEEP[k + 1] + 0.5) * this.sp * SQUEEZE[k]; ctx.strokeStyle = `rgba(213,104,47,${0.35 * this.glow[k]})`; ctx.lineWidth = 9 * U; this.seg(ctx, g, this.c0 - open, this.c0 + open);
    });
    if (!reduced && intro > 0.2) { this.spawnAcc += dt * this.rate * (1 + (this.speed - 1) * 0.8); while (this.spawnAcc >= 1) { this.spawn(); this.spawnAcc--; } }
    const v = this.base * U * (1 + (this.speed - 1) * 0.7);
    for (const d of this.dots) {
      if (d.fade) { d.fade -= dt / 0.35; if (d.fade <= 0) d.dead = true; else this.drawDot(d, d.fade); continue; }
      if (!reduced) d.a += v * d.v * dt;
      while (d.k < 3 && d.a >= G[d.k]) {
        const k = d.k, counts = intro >= 1 && d.counted; if (counts) this.checked[k]++;
        if (d.end === k) { d.a = G[k] - 1; d.fade = 1; break; }
        if (counts) this.keptCount[k]++;
        this.glow[k] = Math.min(1, this.glow[k] + 0.18); d.k++;
      }
      if (d.fade) continue;
      if (d.a >= this.a1) { d.dead = true; if (intro >= 1 && d.counted) this.arrivals++; continue; }
      if (d.a <= reach) this.drawDot(d, 1);
    }
    this.dots = this.dots.filter(d => !d.dead);
    if (this.arrivals && now - this.lastRow > 1300 / this.speed) { this.arrivals = 0; this.lastRow = now; this.addRow(true); }
    this.paintTallies();
    if (!reduced && this.visible && !document.hidden) this.raf = requestAnimationFrame(this.frame);
  };
}
