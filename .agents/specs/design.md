---
version: alpha
name: NexusAgent-Design-System
description: A clean, anti-slop light-mode systems intelligence and architecture observability console inspired by modern enterprise cloud dashboards (Datadog, Linear, Stripe). Anchored on an airy slate-tinted canvas (#F5F6FA), crisp elevated white cards (#FFFFFF), refined hairline borders (#DDE0EB), signature Nexus Indigo (#2C357D) as primary and Slate Blue (#8E97B6) as the secondary hue the neutrals derive from, in three themes (Light, Dark, Black AMOLED), with high-contrast charcoal action pills (#1E232A). Engineered for Next.js 16 + React 19 + shadcn/ui + Tailwind CSS v4, with real-time streaming observability, WCAG 2.2 AA accessibility (4.5:1 text contrast, skip link), and source-passage citation inspection.

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
    font-family-sans: Outfit, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
    font-family-body: Instrument Sans, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
    font-family-mono: JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace
    font-size-xs: 0.75rem
    font-size-sm: 0.875rem
    font-size-base: 1rem
    font-size-lg: 1.125rem
    font-size-xl: 1.25rem
    font-size-2xl: 1.5rem
    font-size-3xl: 1.875rem
    font-weight-regular: '400'
    font-weight-medium: '500'
    font-weight-semibold: '600'
    font-weight-bold: '700'
    line-height-tight: '1.25'
    line-height-normal: '1.5'
    line-height-relaxed: '1.625'

spacing:
    container-padding-desktop: 1.5rem
    container-padding-mobile: 1rem
    element-gap-sm: 0.5rem
    element-gap-md: 0.75rem
    element-gap-lg: 1rem
    card-padding: 1.25rem
    header-height: 3.5rem
    sidebar-width: 17.5rem
    observability-width: 22.5rem

borders:
    radius-sm: 0.25rem
    radius-md: 0.375rem
    radius-lg: 0.5rem
    radius-full: 9999px
    width-hairline: 1px
    width-focus: 2px

motion:
    duration-fast: 150ms
    duration-normal: 250ms
    duration-slow: 350ms
    easing-default: cubic-bezier(0.16, 1, 0.3, 1)
---

## 2. Implementation

- **Components**: shadcn-style primitives in `apps/frontend/components/ui/` (Radix UI + `class-variance-authority`), styled with Tailwind CSS v4.
- **Tokens**: defined once in [`apps/frontend/styles/globals.css`](../../apps/frontend/styles/globals.css): CSS variables under `:root` (light), `.dark` and `.dark.black` (AMOLED overrides of surfaces only), exposed to Tailwind through `@theme` (`bg-primary`, `text-muted-foreground`, `border-border`, `bg-success-bg`, ...). Do not copy hex values into components; add or change a token instead.
- **Type scale**: answer body `text-sm` (14 px); code and tables use the `text-code` token (13 px); interface chrome is `text-xs` (12 px) and never smaller. Fonts: Outfit (headings), Instrument Sans (body), JetBrains Mono (code), loaded with `next/font`.
- **Theme**: `light | dark | black`, logic in `apps/frontend/lib/theme.ts`. Classes on `<html>`: none, `dark`, or `dark black` (black stacks on dark so every `dark:` utility still applies). Set before paint by a nonce-protected inline script in `app/layout.tsx`, persisted in `localStorage` (`nexusagent_theme`), and also updates `<meta name="theme-color">`. Switched from the header button (cycles Light, Dark, Black) or the account menu's segmented radio group.

---

## 3. Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Header: logo · theme toggle · telemetry toggle · quota badge · account      │
├──────────────┬───────────────────────────────────────┬────────────────────┤
│ Workspace    │ Chat canvas                           │ Observability      │
│ - Documents  │  toolbar (New chat, guest note)       │ - pipeline steps   │
│   (upload and│  thread: answers with [S1] pills,     │ - first-token/total│
│   delete for │          tables, sources              │ - grounding badge  │
│   admins     │  quota notice (with refill time)      │ - plan             │
│   only)      │  composer                             │ - run log          │
│ - Chats      │                                       │                    │
│ - MCP connect│                                       │                    │
│   card       │                                       │                    │
└──────────────┴───────────────────────────────────────┴────────────────────┘
```

Below the `xl` breakpoint the three panels become tabs (Workspace / Canvas / Observe) in a bottom bar. The observability panel is hidden by default on desktop and toggled from the header.

### 3.1 Chat canvas

- Answers render Markdown (GFM tables, callouts `> [!NOTE]`, numbered section headings, code with copy button). Raw HTML is never rendered.
- Citations: the answer cites sources as `[S1]`. A pill shows the source label, the filename and, for PDFs, the page number with a hover preview; clicking opens a dialog with the full passage. A "Sources" row lists every source the model saw.
- States: empty (starter prompts that the bundled knowledge base can answer), streaming (status text per pipeline step, then live text with a cursor), error (message + Retry), stopped (Regenerate), quota exhausted (notice with the refill time; Send disabled).
- Guests see a note that their chats are not saved and do not carry context.

### 3.2 Workspace panel

Collapsible sections: **Documents** (the knowledge-base documents; admins can upload and delete (two-step confirm)), **Chats** (Google users: search, grouped by recency, delete with confirm), **MCP Protocol** (MCP (public connection instructions; no sign-in needed)).

---

## 4. Accessibility

Target: **WCAG 2.2 AA**. Implemented:

- Text contrast of at least 4.5:1 for every token pair (checked for light, dark and black themes; the lowest pair is primary on accent in dark at about 4.6:1). Primary buttons use white on `#2C357D` in every theme (11:1); primary text on dark is `#7F88D2` (4.6:1 minimum, on accent).
- Visible focus ring on all interactive elements (2 px, offset 2 px). Interactive controls meet a 36 px minimum target (primary buttons 44 px).
- Skip link ("Skip to chat") jumps to `#main-canvas`.
- Landmarks (`banner`, `main`, `complementary`, `nav`), labelled dialogs with focus trapping (Radix), and a polite live region announcing run status.

Not claimed: WCAG AAA (7:1 contrast and 44 px targets everywhere).

---

## 5. Motion

Short (about 150 ms) transitions on hover and press; a pulsing cursor while streaming; spinners for loading. Nothing animates continuously otherwise.
