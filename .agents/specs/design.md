---
version: alpha
name: AIRankAgent-Design-System
description: A clean, anti-slop light-mode systems intelligence and architecture observability console inspired by modern enterprise cloud dashboards (Datadog, Linear, Stripe). Anchored on an airy slate-tinted canvas (#F5F6FA), crisp elevated white cards (#FFFFFF), refined hairline borders (#DDE0EB), signature AIRank Indigo (#2C357D) as primary and Slate Blue (#8E97B6) as the secondary hue the neutrals derive from, in three themes (Light, Dark, Black AMOLED), with high-contrast charcoal action pills (#1E232A). Engineered for Next.js 16 + React 19 + shadcn/ui + Tailwind CSS v4, with real-time streaming observability, WCAG 2.2 AA accessibility (4.5:1 text contrast, skip link), and line-level citation inspection.

colors:
    primary: '#2c357d'
    primary-hover: '#222a66'
    primary-dark: '#222a66'
    primary-subtle: '#e8eaf6'
    primary-border: '#b4bad3'
    primary-fill: '#2c357d'
    primary-on-dark: '#7f88d2'
    brand-secondary: '#8e97b6'
    dark-pill: '#1e232a'
    dark-pill-hover: '#0a0d12'
    ink: '#141833'
    ink-secondary: '#334155'
    body: '#1e293b'
    muted: '#545c7a'
    muted-bg: '#eef0f6'
    border: '#c3c8da'
    border-subtle: '#dde0eb'
    input-border: '#64748b'
    canvas: '#f5f6fa'
    canvas-subtle: '#eaedf2'
    surface-card: '#ffffff'
    surface-card-elevated: '#ffffff'
    status-valid: '#14532d'
    status-valid-bg: '#ecfdf5'
    status-valid-border: '#86efac'
    status-warning: '#78350f'
    status-warning-bg: '#fffbeb'
    status-warning-border: '#fcd34d'
    status-danger: '#991b1b'
    status-danger-bg: '#fef2f2'
    status-danger-border: '#fca5a5'
    citation-pill: '#e8eaf6'
    citation-pill-border: '#b4bad3'
    citation-pill-text: '#2c357d'
    citation-pill-hover: '#dfe2f2'

shadows:
    xs: '0 1px 2px rgba(0, 0, 0, 0.03)'
    sm: '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)'
    card: '0 1px 3px rgba(0, 0, 0, 0.03), 0 6px 16px -2px rgba(0, 0, 0, 0.03)'
    dropdown: '0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04)'
    modal: '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)'

typography:
    display-xl:
        fontFamily: 'Outfit, system-ui, sans-serif'
        fontSize: 32px
        fontWeight: 700
        lineHeight: 1.15
        letterSpacing: -0.5px
    display-lg:
        fontFamily: 'Outfit, system-ui, sans-serif'
        fontSize: 24px
        fontWeight: 700
        lineHeight: 1.2
        letterSpacing: -0.3px
    title-md:
        fontFamily: "'Instrument Sans', system-ui, sans-serif"
        fontSize: 16px
        fontWeight: 600
        lineHeight: 1.35
        letterSpacing: -0.1px
    title-sm:
        fontFamily: "'Instrument Sans', system-ui, sans-serif"
        fontSize: 14px
        fontWeight: 600
        lineHeight: 1.4
        letterSpacing: 0
    body-md:
        fontFamily: "'Instrument Sans', system-ui, sans-serif"
        fontSize: 14px
        fontWeight: 400
        lineHeight: 1.5
        letterSpacing: 0
    body-sm:
        fontFamily: "'Instrument Sans', system-ui, sans-serif"
        fontSize: 12px
        fontWeight: 400
        lineHeight: 1.45
        letterSpacing: 0
    code:
        fontFamily: 'JetBrains Mono, monospace'
        fontSize: 13px
        fontWeight: 500
        lineHeight: 1.5
        letterSpacing: -0.2px
---

# AIRankAgent — UI/UX Design System

## 1. Design philosophy

A calm, light-first console for engineers reading long technical answers. Soft slate-tinted canvas (`#F5F6FA`), white elevated cards, one signature indigo (`#2C357D`) for actions and links, and restrained motion. Slate Blue (`#8E97B6`) is the secondary brand hue: neutrals (surfaces, borders, muted text) are tints and shades of it, and `brand-secondary` carries it for decorative accents (featured and citation borders), never body text on light. Three themes share the same tokens: Light, Dark (navy-charcoal) and Black (true `#000` for AMOLED). Primary is split by role so the brand colour never changes between themes: `primary-fill` (buttons, badges, user bubble, logo) is `#2C357D` in every theme, with white text at 11:1. `primary` (text, icons, borders, rings, tints) is `#2C357D` on light; on dark and black it is the same hue and saturation (233°, 48%) lifted only to `#7F88D2`, the lowest lightness that clears 4.5:1 on every dark surface. Never put text in raw `#2C357D` on a dark surface. No neon glows or decorative animation.

---

## 2. Implementation

- **Components**: shadcn-style primitives in `apps/frontend/components/ui/` (Radix UI + `class-variance-authority`), styled with Tailwind CSS v4.
- **Tokens**: defined once in [`apps/frontend/styles/globals.css`](../../apps/frontend/styles/globals.css): CSS variables under `:root` (light), `.dark` and `.dark.black` (AMOLED overrides of surfaces only), exposed to Tailwind through `@theme` (`bg-primary`, `text-muted-foreground`, `border-border`, `bg-success-bg`, ...). Do not copy hex values into components; add or change a token instead.
- **Type scale**: answer body `text-sm` (14 px); code and tables use the `text-code` token (13 px); interface chrome is `text-xs` (12 px) and never smaller. Fonts: Outfit (headings), Instrument Sans (body), JetBrains Mono (code), loaded with `next/font`.
- **Theme**: `light | dark | black`, logic in `apps/frontend/lib/theme.ts`. Classes on `<html>`: none, `dark`, or `dark black` (black stacks on dark so every `dark:` utility still applies). Set before paint by a nonce-protected inline script in `app/layout.tsx`, persisted in `localStorage` (`airankagent_theme`), and also updates `<meta name="theme-color">`. Switched from the header button (cycles Light, Dark, Black) or the account menu's segmented radio group.

---

## 3. Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Header: logo · theme toggle · telemetry toggle · quota badge · account      │
├──────────────┬───────────────────────────────────────┬────────────────────┤
│ Workspace    │ Chat canvas                           │ Observability      │
│ - Documents  │  toolbar (New chat, guest note)       │ - pipeline steps   │
│   (upload,   │  thread: answers with [S1] pills,     │ - first-token/total│
│   delete)    │          tables, diagrams, sources    │ - grounding badge  │
│ - Chats      │  quota notice (with refill time)      │ - plan             │
│ - MCP tool   │  composer                             │ - run log          │
│   inspector  │                                       │                    │
└──────────────┴───────────────────────────────────────┴────────────────────┘
```

Below the `xl` breakpoint the three panels become tabs (Workspace / Canvas / Observe) in a bottom bar. The observability panel is hidden by default on desktop and toggled from the header.

### 3.1 Chat canvas

- Answers render Markdown (GFM tables, callouts `> [!NOTE]`, numbered section headings, code with copy button). Raw HTML is never rendered.
- Citations: the answer cites sources as `[S1]`. A pill shows the source label, filename and line range with a hover preview; clicking opens a dialog with the full passage. A "Sources" row lists every source the model saw.
- Mermaid diagrams render as sanitised SVG with zoom, pan, source view and a maximised mode (Escape closes, focus is trapped).
- States: empty (starter prompts that the bundled knowledge base can answer), streaming (status text per pipeline step, then live text with a cursor), error (message + Retry), stopped (Regenerate), quota exhausted (notice with the refill time; Send disabled).
- Guests see a note that their chats are not saved and do not carry context.

### 3.2 Workspace panel

Collapsible sections: **Documents** (seeded benchmarks plus the user's uploads; uploads can be deleted with a two-step confirm), **Chats** (Google users: search, grouped by recency, delete with confirm), **MCP Protocol** (inspector; asks guests to sign in first).

---

## 4. Accessibility

Target: **WCAG 2.2 AA**. Implemented:

- Text contrast of at least 4.5:1 for every token pair (checked for light, dark and black themes; the lowest pair is primary on accent in dark at about 4.6:1). Primary buttons use white on `#2C357D` in every theme (11:1); primary text on dark is `#7F88D2` (4.6:1 minimum, on accent).
- Visible focus ring on all interactive elements (2 px, offset 2 px). Interactive controls meet a 36 px minimum target (primary buttons 44 px).
- Skip link ("Skip to chat") jumps to `#main-canvas`.
- Landmarks (`banner`, `main`, `complementary`, `nav`), labelled dialogs with focus trapping (Radix), and a polite live region announcing run status.
- Diagram viewport is keyboard operable (arrows pan, `+`/`-` zoom, `0` resets).

Not claimed: WCAG AAA (7:1 contrast and 44 px targets everywhere).

---

## 5. Motion

Short (about 150 ms) transitions on hover and press; a pulsing cursor while streaming; spinners for loading. Nothing animates continuously otherwise.
