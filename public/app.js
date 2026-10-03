// ScreenCare in the browser: displays, counts down, remembers.
// Every decision is made by the Python API (/api/act); this file only renders
// the session it gets back, stores it locally, and reports presence.

const STORE_KEY = "screencare:v1";
const HEARTBEAT_MS = 15_000;
const GAP_MS = 120_000; // a silence longer than this means the user was away
const EYE_REST_MS = 20_000;
const RING = 2 * Math.PI * 108;

// Defaults match the design tokens in styles/app.css.
const DEFAULT_COLORS = { focus: "#8a81ef", recover: "#4bc39f" };
const POSTPONE_COLOR = "#f2af48"; // deliberately not customizable: it signals "overdue"
const PALETTE = {
  focus: [
    { name: "Violet", hex: "#8a81ef" },
    { name: "Indigo", hex: "#6f86f0" },
    { name: "Ocean", hex: "#3fa7d6" },
    { name: "Rose", hex: "#ec7aa3" },
    { name: "Coral", hex: "#f08a6c" },
  ],
  recover: [
    { name: "Teal", hex: "#4bc39f" },
    { name: "Sage", hex: "#8fbf7a" },
    { name: "Sky", hex: "#57b8e3" },
    { name: "Sand", hex: "#d8b37a" },
    { name: "Lilac", hex: "#b59cf0" },
  ],
};
const HEX = /^#[0-9a-f]{6}$/i;

// On-screen copy comes from screencare/messages.py. A variant is chosen by
// hashing a seed that stays fixed for the whole phase, so text never changes
// mid-phase but each new block or break can read differently.
const COPY = window.SCREENCARE.copy;
const hash = (text) => {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.codePointAt(0), 16777619);
  return h >>> 0;
};
const variant = (key, seed) => COPY[key][hash(`${key}|${seed}`) % COPY[key].length];

// Black or white, whichever reads better on `hex` (WCAG relative luminance).
const inkFor = (hex) => {
  const lin = (i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const L = 0.2126 * lin(1) + 0.7152 * lin(3) + 0.0722 * lin(5);
  return (L + 0.05) / 0.05 >= 1.05 / (L + 0.05) ? "#0c0a09" : "#ffffff";
};

const cleanColors = (colors) => ({
  focus: HEX.test(colors?.focus) ? colors.focus.toLowerCase() : DEFAULT_COLORS.focus,
  recover: HEX.test(colors?.recover) ? colors.recover.toLowerCase() : DEFAULT_COLORS.recover,
});

const load = () => {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY)) || {};
  } catch {
    return {};
  }
};

const fmt = (s) => {
  s = Math.max(0, Math.ceil(s));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

document.addEventListener("alpine:init", () => {
  Alpine.data("screencare", () => {
    const saved = load();
    return {
      RING,
      PALETTE,
      session: saved.session || null,
      settings: { ...window.SCREENCARE.defaults, ...saved.settings },
      // Anyone with history has effectively been onboarded already.
      prefs: {
        theme: "system",
        idle: false,
        onboarded: !!saved.history?.length,
        ...saved.prefs,
        colors: cleanColors(saved.prefs?.colors),
      },
      history: saved.history || [],
      lastBeat: saved.lastBeat || 0,
      now: Date.now(),
      skew: 0,
      busy: false,
      view: "focus",
      mode: saved.prefs?.mode || "adaptive",
      task: "",
      note: "",
      toasts: [],
      summary: null,
      settingsOpen: false,
      colorsOpen: false,
      feedbackFor: null,
      picked: {},
      notifyPerm: "Notification" in window ? Notification.permission : "unsupported",
      idleSupported: "IdleDetector" in window,
      idleOn: false,
      suggestions: [
        { id: "walk", emoji: "🚶", label: "Walk around" },
        { id: "water", emoji: "💧", label: "Get water" },
        { id: "eyes", emoji: "👀", label: "Look far away" },
        { id: "stretch", emoji: "🙆", label: "Stretch" },
      ],

      async init() {
        this.session ??= { phase: "idle", adaptive_focus_s: 1500, extensions_used: 0 };
        const gap = this.lastBeat && Date.now() - this.lastBeat > GAP_MS;
        await (gap ? this.act("back", { since: new Date(this.lastBeat).toISOString() }) : this.act("sync"));
        if (this.prefs.idle && this.idleSupported) this.enableIdle(true);
        setInterval(() => this.tick(), 1000);
        matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => this.applyTheme());
        this.applyTheme();
      },

      // -- talking to the rules ------------------------------------------------

      // Actions run one at a time, so each starts from the session the previous
      // one returned. A sync is skipped if anything is already queued.
      queue: Promise.resolve(),
      pending: 0,

      act(action, payload = {}) {
        if (action === "sync" && this.pending) return Promise.resolve(false);
        this.pending++;
        const run = this.queue.then(() => this.send(action, payload));
        this.queue = run.finally(() => this.pending--);
        return run;
      },

      async send(action, payload) {
        this.busy = true;
        try {
          const res = await fetch("/api/act", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session: this.session, settings: this.settings, action, payload }),
          });
          const body = await res.json();
          if (!res.ok) {
            this.toast(typeof body.detail === "string" ? body.detail : "That didn't work. Try again.");
            return false;
          }
          this.skew = Date.parse(body.server_now) - Date.now();
          this.session = body.session;
          body.events.forEach((e) => this.handle(e));
          this.save();
          return true;
        } catch {
          this.toast("You're offline. ScreenCare will catch up when you reconnect.");
          return false;
        } finally {
          this.busy = false;
        }
      },

      handle(e) {
        if (e.event === "record") {
          const { event, ...record } = e;
          this.history.push(record);
        } else if (e.event === "notify") {
          if (document.hidden && this.notifyPerm === "granted") {
            new Notification(e.title, { body: e.body, tag: e.type, icon: "/icons/icon.svg" });
          } else if (e.type !== "recovery") {
            // The recovery screen itself says it's break time; a toast would repeat it.
            this.toast(`${e.title} ${e.body}`, e.type);
          }
        } else if (e.event === "banner") {
          const ms = e.type === "eye_rest" ? EYE_REST_MS : 12_000;
          this.toast(e.text, e.type, ms);
        }
      },

      save() {
        this.lastBeat = Date.now();
        const history = this.history.slice(-20_000);
        try {
          localStorage.setItem(
            STORE_KEY,
            JSON.stringify({
              session: this.session,
              settings: this.settings,
              prefs: { ...this.prefs, mode: this.mode },
              history,
              lastBeat: this.lastBeat,
            }),
          );
        } catch {}
      },

      // -- clock -------------------------------------------------------------------

      tick() {
        const real = Date.now();
        if (real - this.lastBeat > GAP_MS) {
          // The tab was frozen or the machine slept: report the gap as away time.
          const since = new Date(this.lastBeat).toISOString();
          this.lastBeat = real;
          this.act("back", { since });
          return;
        }
        this.now = real + this.skew;
        if (real - this.lastBeat > HEARTBEAT_MS) this.save();
        const s = this.session;
        const due = [s.focus, s.rest, s.hydration, s.eye].some((t) => t?.due_at && Date.parse(t.due_at) <= this.now);
        if (due) this.act("sync");
      },

      left(timer) {
        if (!timer) return 0;
        if (timer.due_at) return Math.max(0, (Date.parse(timer.due_at) - this.now) / 1000);
        return timer.left_s ?? 0;
      },

      get liveActive() {
        const s = this.session;
        const extra = s.active_since ? (this.now - Date.parse(s.active_since)) / 1000 : 0;
        return (s.active_s || 0) + Math.max(0, extra);
      },

      get remaining() {
        const p = this.session.phase;
        if (p === "focusing" || p === "paused") return this.left(this.session.focus);
        if (p === "breaking" || p === "idea_walk") return this.left(this.session.rest);
        if (p === "idle") return this.modeSeconds(this.mode);
        return this.session.recovery_s || 0; // recovery due: show the suggested break length
      },

      get clock() {
        return fmt(this.remaining);
      },

      get ariaClock() {
        return `${Math.ceil(this.remaining / 60)} minutes left`;
      },

      get progress() {
        const s = this.session;
        if (s.phase === "focusing" || s.phase === "paused") return Math.min(1, this.liveActive / (s.planned_s || 1));
        if (s.phase === "recovery_due") return 1;
        if (s.phase === "breaking") return 1 - this.left(s.rest) / (s.recovery_s || 1);
        if (s.phase === "idea_walk") return 1 - this.left(s.rest) / 300;
        return 0;
      },

      modeSeconds(mode) {
        return { classic: 1500, deep: 3000 }[mode] ?? this.session.adaptive_focus_s;
      },

      // -- presentation ---------------------------------------------------------

      get postponed() {
        return this.session.extensions_used > 0 || this.session.finish_thought_used;
      },

      get overtime() {
        return this.session.phase === "focusing" && this.liveActive >= this.session.planned_s;
      },

      get accent() {
        const p = this.session.phase;
        const { focus, recover } = this.prefs.colors;
        if (p === "breaking" || p === "idea_walk") return recover;
        if (p === "recovery_due") return this.postponed ? POSTPONE_COLOR : recover;
        if (this.overtime) return POSTPONE_COLOR;
        return focus;
      },

      get themeVars() {
        const { focus, recover } = this.prefs.colors;
        return {
          "--accent": this.accent,
          "--accent-ink": inkFor(this.accent),
          "--color-focus": focus,
          "--color-recover": recover,
          "--recover-ink": inkFor(recover),
        };
      },

      setColor(kind, hex) {
        if (!HEX.test(hex)) return;
        this.prefs.colors = { ...this.prefs.colors, [kind]: hex.toLowerCase() };
        this.save();
      },

      isCustomColor(kind) {
        return !PALETTE[kind].some((c) => c.hex === this.prefs.colors[kind]);
      },

      get isDefaultColors() {
        const c = this.prefs.colors;
        return c.focus === DEFAULT_COLORS.focus && c.recover === DEFAULT_COLORS.recover;
      },

      resetColors() {
        this.prefs.colors = { ...DEFAULT_COLORS };
        this.save();
      },

      // A gentle pulse keeps the ring alive while ready or focusing; paused stays still.
      get calmBreath() {
        return ["idle", "focusing", "recovery_due"].includes(this.session.phase);
      },

      get breathing() {
        return this.session.phase === "breaking" || this.session.phase === "idea_walk";
      },

      get phaseLabel() {
        return {
          idle: "Ready",
          focusing: this.overtime ? "Extra time" : "Focusing",
          paused: "Paused",
          recovery_due: "Break time",
          breaking: "Recovering",
          idea_walk: "Idea walk",
        }[this.session.phase];
      },

      get subline() {
        const p = this.session.phase;
        if (p === "idle") return { adaptive: "Adaptive", classic: "Classic", deep: "Deep focus" }[this.mode];
        if (p === "recovery_due") return `${Math.round(this.liveActive / 60)} focused minutes`;
        return "";
      },

      get screenCopy() {
        const s = this.session;
        switch (s.phase) {
          case "idle":
            return variant("idle", this.history.length);
          case "focusing":
            return variant(this.overtime ? "overtime" : "focusing", s.started_at);
          case "paused":
            return variant("paused", s.started_at);
          case "recovery_due": {
            const key = this.extensionsLeft === 0 ? "postponed_max" : this.postponed ? "postponed" : "recovery";
            return variant(key, `${s.started_at}|${s.extensions_used}|${s.finish_thought_used}`);
          }
          case "breaking":
          case "idea_walk":
            return variant(s.phase, s.break_started_at);
          default:
            return ["", ""];
        }
      },

      get extensionsLeft() {
        return Math.max(0, window.SCREENCARE.maxExtensions - (this.session.extensions_used || 0));
      },

      get isQuiet() {
        return !!this.session.quiet_until && Date.parse(this.session.quiet_until) > this.now;
      },

      get quietLeft() {
        return this.isQuiet ? `${Math.ceil((Date.parse(this.session.quiet_until) - this.now) / 60000)} min left` : "";
      },

      get isAway() {
        return !!this.session.away_since;
      },

      // -- actions -----------------------------------------------------------------

      finishOnboarding() {
        this.prefs.onboarded = true;
        this.save();
      },

      async start() {
        this.enableNotifications();
        if (await this.act("start", { mode: this.mode, task: this.task })) this.task = "";
      },

      askFeedback(action) {
        this.feedbackFor = action;
      },

      async finishWith(feedback) {
        const action = this.feedbackFor;
        this.feedbackFor = null;
        await this.act(action, feedback ? { feedback } : {});
        this.picked = {};
      },

      async returnFromWalk(resume) {
        if (await this.act("return", { note: this.note, resume })) this.note = "";
      },

      stepAway() {
        this.act("away");
      },

      drink() {
        this.act("drink").then((ok) => ok && this.toast(variant("drink", Date.now())));
      },

      toggleQuiet() {
        this.act("quiet", { minutes: this.isQuiet ? 0 : this.settings.quiet_minutes });
      },

      saveSettings() {
        this.save();
      },

      // -- toasts ------------------------------------------------------------------

      toast(text, type = "info", ms = 8000) {
        const t = { id: crypto.randomUUID(), text, type };
        this.toasts = [...this.toasts.filter((x) => x.type !== type || type === "info"), t].slice(-3);
        setTimeout(() => this.closeToast(t), ms);
      },

      closeToast(t) {
        if (!this.toasts.includes(t)) return;
        this.toasts = this.toasts.filter((x) => x !== t);
        if (t.type === "eye_rest") this.act("dismiss");
      },

      // -- browser integrations ---------------------------------------------------------

      async enableNotifications() {
        if (this.notifyPerm !== "default") return;
        this.notifyPerm = await Notification.requestPermission();
      },

      async enableIdle(silent = false) {
        if (!this.idleSupported || this.idleOn) return;
        try {
          if ((await IdleDetector.requestPermission()) !== "granted") throw new Error();
          const detector = new IdleDetector();
          const threshold = 90_000;
          detector.addEventListener("change", () => {
            const away = detector.userState === "idle" || detector.screenState === "locked";
            if (away && !this.isAway) {
              this.act("away", { since: new Date(Date.now() + this.skew - threshold).toISOString() });
            } else if (!away && this.isAway) {
              this.act("back");
            }
          });
          await detector.start({ threshold });
          this.idleOn = true;
          this.prefs.idle = true;
          this.save();
        } catch {
          if (!silent) this.toast("Idle detection wasn't allowed. You can still use “Step away”.");
        }
      },

      applyTheme() {
        const t = this.prefs.theme;
        const dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
        document.documentElement.dataset.theme = dark ? "dark" : "light";
      },

      setTheme(t) {
        this.prefs.theme = t;
        this.applyTheme();
        this.save();
      },

      // -- dashboard ---------------------------------------------------------------

      async openDashboard() {
        this.view = "dashboard";
        try {
          const res = await fetch("/api/summary", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ records: this.recentHistory(8), tz_offset_minutes: -new Date().getTimezoneOffset() }),
          });
          if (res.ok) this.summary = await res.json();
        } catch {
          this.toast("Couldn't load the dashboard while offline.");
        }
      },

      recentHistory(days) {
        const cutoff = Date.now() - days * 86_400_000;
        return this.history.filter((r) => Date.parse(r.ended_at || r.at) >= cutoff);
      },

      get tiles() {
        const t = this.summary.today;
        const n = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;
        return [
          { label: "Focused", value: `${t.focus_minutes}m`, hint: `${n(t.sessions, "block")} · longest ${t.longest_session_minutes}m` },
          { label: "Breaks taken", value: t.breaks_taken, hint: `${t.breaks_skipped} skipped · ${n(t.walks, "walk")}` },
          { label: "Away from screen", value: `${t.away_minutes}m`, hint: "noticed automatically" },
          { label: "Water", value: t.drinks, hint: t.ideas ? `${n(t.ideas, "idea")} captured too` : "drinks logged" },
        ];
      },

      barHeight(minutes) {
        const max = Math.max(60, ...this.summary.trend.map((d) => d.focus_minutes));
        return (minutes / max) * 150;
      },

      get trendLabel() {
        return "Focused minutes per day: " + this.summary.trend.map((d) => `${d.label} ${d.focus_minutes}`).join(", ");
      },

      // -- data ----------------------------------------------------------------------

      exportData() {
        const blob = new Blob([localStorage.getItem(STORE_KEY) || "{}"], { type: "application/json" });
        const a = Object.assign(document.createElement("a"), {
          href: URL.createObjectURL(blob),
          download: `screencare-${new Date().toISOString().slice(0, 10)}.json`,
        });
        a.click();
        URL.revokeObjectURL(a.href);
      },

      async importData(event) {
        const file = event.target.files[0];
        if (!file) return;
        try {
          const data = JSON.parse(await file.text());
          if (!Array.isArray(data.history)) throw new Error();
          localStorage.setItem(STORE_KEY, JSON.stringify(data));
          location.reload();
        } catch {
          this.toast("That file doesn't look like a ScreenCare export.");
        }
      },

      resetAll() {
        if (!confirm("Erase all ScreenCare history and settings from this browser?")) return;
        localStorage.removeItem(STORE_KEY);
        location.reload();
      },
    };
  });
});

if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
