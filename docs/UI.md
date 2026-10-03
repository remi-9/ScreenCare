# UI direction

ScreenCare should feel like a calm room, not a dashboard. It should be modern
and characterful, but never loud: the app's whole job is to make the user
*less* glued to the screen, so the UI should never compete for attention.

## Stack

| Piece | Choice | Why |
|---|---|---|
| Markup | Jinja2 templates rendered by FastAPI | Python stays the main language; one place for copy and structure |
| Styling | Tailwind CSS v4 via [`pytailwindcss`](https://pypi.org/project/pytailwindcss/) | Modern utility styling with no Node toolchain; built `public/app.css` is committed |
| Interactivity | Alpine.js 3 (pinned, jsdelivr) | Small, declarative, lives in the HTML. Enough for a countdown, toasts, and forms |
| Icons | Lucide, inlined as SVG partials | Consistent stroke icons, no icon font |
| Fonts | Google Fonts: **Fraunces** (display) + **Inter** (UI, tabular digits) | A soft serif for phase headlines gives warmth and character; Inter keeps controls crisp |

No component kit by default. A small set of design tokens (below) and
hand-built components is what keeps it from looking like every other
Tailwind template.

### Component sources (surveyed October 2026)

| Use | Repo | License | How |
|---|---|---|---|
| Focus trap for dialogs/sheets | [alpinejs/alpine](https://github.com/alpinejs/alpine) Focus plugin (`x-trap.inert.noscroll`) | MIT | CDN script before Alpine core |
| Icons | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | Static SVGs inlined in `templates/icons.html` |
| Reference / drop-in kit if more components are needed | [hunvreus/basecoat](https://github.com/hunvreus/basecoat): shadcn look, Tailwind v4, ships Jinja macros | MIT | Copy individual components; audit ARIA ourselves |
| Alternative kit | [saadeghi/daisyui](https://github.com/saadeghi/daisyui) v5 (works with the standalone CLI via `daisyui.mjs`) | MIT | Not adopted: generic look, accordion/tabs need extra ARIA |
| Copy-paste patterns | [thedevdojo/pines](https://github.com/thedevdojo/pines) (Alpine + Tailwind v3), [markmead/hyperui](https://github.com/markmead/hyperui) | MIT | Inspiration for toast and sheet markup |
| Timer UX inspiration | [Splode/pomotroid](https://github.com/Splode/pomotroid) | MIT | Look only |

Avoid **Preline** (custom "Fair Use" license, revocable) and **Flowbite**
(needs npm for its plugin). Avoid copying code from GPL apps (GoodTime,
Tomato). Charts are hand-written SVG; frappe-charts is stale and uPlot is
canvas-only, which hurts accessibility. No library makes verified WCAG claims,
so the accessibility checklist below applies to every component.

## Look and feel

- **Dark-first, warm neutrals.** Base on stone/warm gray, not blue-black.
  Light theme follows `prefers-color-scheme`, with a manual toggle in Settings.
- **One accent per phase**, so the screen tells you where you are at a glance:
  - Focus: indigo → violet
  - Recovery / break: teal → green
  - Hydration: sky
  - Postponed recovery: amber (warmer, never red)
- **Slow ambient gradient** behind the content that shifts to the current
  phase's hue over a few seconds. Static under `prefers-reduced-motion`.
- **Soft glass cards**: subtle translucency and blur, generous radius
  (`rounded-3xl`), hairline borders instead of heavy shadows.
- **Signature element: the breathing ring.** Layers driven by one breath
  (4 s in, 6 s out): a solid "lung" ring (white in dark theme, the accent in
  light) that swells past the progress ring, ripples released at the top of
  each breath, two slowly morphing color shapes, three orbiting points of
  light, and a "Breathe in… / …and out" cue. The page background breathes
  too: the phase-colored light swells while a warm light opposite moves
  against it. Gentle (60%) while ready or focusing, full during breaks, still
  when paused, and fully still under reduced motion.
- **Your colors.** The palette button in the header (next to water and quiet
  mode) opens a quick color popover, and Settings → Appearance has a *Focus color* and a *Break
  color*: five curated swatches each, plus a custom color picker. Button text
  switches between near-black and white automatically, whichever contrasts
  better. The amber "postponed" color stays fixed, because it means
  "overdue".
- **Copy is kind and short.** "Time for a reset." "Anything come to mind?" Every message has a few
  variations, all in `screencare/messages.py`. Server messages (notifications,
  banners) are picked per moment. On-screen headlines are picked once per
  phase, keyed to when the phase started, so they never change mid-phase but
  each block reads a little differently. Buttons never vary, because
  predictable controls matter more than variety.
  No exclamation marks, no guilt, no streaks.

### Design tokens (`styles/app.css`, `@theme`)

```css
@theme {
  --font-display: "Fraunces", ui-serif, Georgia, serif;
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --color-focus: oklch(0.62 0.17 285);
  --color-recover: oklch(0.70 0.13 170);
  --color-hydrate: oklch(0.72 0.12 230);
  --color-postpone: oklch(0.78 0.14 75);
  --radius-card: 1.5rem;
}
```

### Breathing, technically

`--breath` and `--breath-amp` are registered with `@property` so the browser
can interpolate them. Layers use `scale: calc(1 + k * var(--breath) *
var(--breath-amp))`. Keep the cue spans rendered (never `display: none`), or
their animation would restart out of step with the breath. Write `animation`
shorthands with a name: Tailwind's minifier turns a name-less one into
`animation: none`.

## Screens

All on one page. Alpine swaps the view from `session.phase`, so there's no
client-side router.

1. **Start**: segmented control for Classic / Deep / Adaptive (shows the
   minutes each will run), optional "What do you want to accomplish?" input,
   big *Start focus* button.
2. **Focusing**: ring + `mm:ss`, task label, *Pause*, *I'm stuck*. Eye-rest
   prompt appears as a small pill at the top ("👀 Look far away for 20
   seconds") that fades out by itself. Nothing modal.
3. **Recovery due**: phase headline in Fraunces, three equal choices:
   *Start break* · *Finish this thought* · *+5 min (1 left)*. Each extension
   warms the accent toward amber and makes the copy a little firmer.
4. **Break**: breathing ring, countdown, suggestion chips (🚶 Walk · 💧 Water
   · 👀 Distance · 🙆 Stretch) the user can tap, purely for themselves and
   not tracked as a score. Ends with *How was that focus block?* → Too short /
   Just right / Too long.
5. **Idea Walk**: 5-minute ring, "Step away. Don't force it." On return, a
   single textarea: *Anything come to mind?*
6. **Dashboard** (drawer or second tab): today's stat tiles plus a 7-day bar
   chart of focused minutes vs breaks. Inline SVG, no chart library.
7. **Settings** (side sheet): durations, hydration interval + strict mode,
   eye-rest toggle, quiet mode, theme, notification/idle permissions,
   export/import data.

## Accessibility checklist

Verified with axe-core in Edge (both themes, 390 px and 1280 px, every
phase). A manual screen-reader pass is still worth doing before launch.

"Accessible" means both *reachable* (it's a URL; no install, no account) and
*usable by everyone*:

- [x] WCAG 2.2 AA contrast in both themes, checked on every phase accent.
- [x] Every action works by keyboard. Visible focus rings (`focus-visible`),
      logical tab order, `Esc` closes sheets.
- [x] Phase changes are announced through one `aria-live="polite"` region.
      The ticking timer is *not* live, to avoid a screen reader announcing
      every second. The ring has `role="progressbar"` with `aria-valuenow`
      updated each minute.
- [x] Never rely on color alone: every phase has an icon and a text label.
- [x] `prefers-reduced-motion` stops the gradient drift and breathing ring.
- [x] Sizes in `rem`, layout holds at 200% zoom and at 320 px width.
      Touch targets ≥ 44 px.
- [x] Notification and idle-detection permissions are requested in context,
      with a one-line plain-language reason, and the app works fully if they're
      declined.
