---
version: alpha
name: NexusAgent-Design-System
description: A clean, anti-slop light-mode systems intelligence and architecture observability console inspired by modern enterprise cloud dashboards (Datadog, Linear, Stripe). Anchored on an airy neutral canvas (#F4F5F8), crisp elevated white cards (#FFFFFF), refined hairline borders (#CBD5E1), and signature Nexus Blue (#004EA1) accents with high-contrast charcoal action pills (#1E232A). Engineered for Next.js 16 + React 19 + shadcn/ui + Tailwind CSS v4, with sub-second real-time streaming observability, WCAG 2.2 AAA accessibility compliance (7:1 text contrast, 3:1 non-text contrast, 44px target sizes, skip links), interactive architecture topology nodes, and line-level citation inspection.

colors:
    primary: '#004ea1'
    primary-hover: '#003673'
    primary-dark: '#004182'
    primary-subtle: '#e8f3fc'
    primary-border: '#93c5fd'
    dark-pill: '#1e232a'
    dark-pill-hover: '#0a0d12'
    ink: '#0f172a'
    ink-secondary: '#334155'
    body: '#1e293b'
    muted: '#475569'
    muted-bg: '#f1f5f9'
    border: '#cbd5e1'
    border-subtle: '#e2e8f0'
    input-border: '#64748b'
    canvas: '#f4f5f8'
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
    citation-pill: '#e8f3fc'
    citation-pill-border: '#93c5fd'
    citation-pill-text: '#004182'
    citation-pill-hover: '#d8ecf9'

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

# NexusAgent — UI/UX Design System Specification

## 1. Design Philosophy: Anti-Slop, Clean Light Systems Intelligence

NexusAgent is engineered for Staff-Plus Systems Engineers, VP of Engineering, and CTOs who evaluate mission-critical distributed architectures. The visual identity avoids the dark "AI slop" cliche (neon glows, purple/cyan gradients, low-contrast text) in favor of **clarity, high density, and cryptographic precision**, modeled on world-class observability consoles.

- **Airy Neutral Canvas**: Soft grey `#F4F5F8` foundation provides comfortable daytime reading and high contrast for technical reviews and architectural auditing.
- **Crisp Elevated Cards**: Pure white `#FFFFFF` cards with subtle borders (`#E2E8F0`) and soft pillowy elevation (`box-shadow: 0 1px 3px rgba(0,0,0,0.03), 0 6px 16px -2px rgba(0,0,0,0.03)`).
- **Nexus Blue Signature Accent**: Professional `#004EA1` denotes active states, links, and primary CTA triggers, paired with `#E8F3FC` light tint chips and `#1E232A` dark action pills.
- **Architecture Flow Topology**: Node cards with clean headers (e.g. `Radis-Master`, `sdkclient.eng...`, `Neon-Storage`), sub-metrics rows (`150 kbps ↗`), and clean status indicators.
- **Data-Dense Telemetry Panels**: TCP throughput bar charts with clean categorical segments (high red, medium amber, low blue) and structured service overview tables.

---

## 2. Component Integration: Next.js 16 + shadcn/ui + Tailwind v4

NexusAgent integrates **shadcn/ui** primitives powered by **Tailwind CSS v4** native CSS variables and `@theme` directives:

### 2.1 Tailwind CSS v4 Configuration (`apps/frontend/styles/globals.css`)

```css
@import 'tailwindcss';

@theme {
    --color-background: #f4f5f8;
    --color-foreground: #0f172a;
    --color-card: #ffffff;
    --color-card-foreground: #0f172a;
    --color-popover: #ffffff;
    --color-popover-foreground: #0f172a;
    --color-primary: #0a66c2;
    --color-primary-foreground: #ffffff;
    --color-secondary: #f1f5f9;
    --color-secondary-foreground: #0f172a;
    --color-muted: #f1f5f9;
    --color-muted-foreground: #64748b;
    --color-accent: #e8f3fc;
    --color-accent-foreground: #0a66c2;
    --color-destructive: #dc2626;
    --color-destructive-foreground: #ffffff;
    --color-border: #e2e8f0;
    --color-input: #e2e8f0;
    --color-ring: #0a66c2;
    --font-sans: 'Instrument Sans', system-ui, -apple-system, sans-serif;
    --font-heading: 'Outfit', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
}
```

---

## 3. Command Center Layout (Modeled on Sample Directory)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER: [NexusAgent] | Interval: [last 5 min] | [Breakdown ▼] | [Quick search...] | [Load ▼] | [1-Click]       │
├───────┬────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ RAIL  │ TOP SECTION: Architecture Topology / Distributed Cluster Nodes (Radis-Master -> sdkclient -> Neon)    │
│  [■]  │  - Node Cards with Nexus Blue headers, status pills, and sub-metrics (US-east-lb: 150 kbps)            │
│  [📁] ├──────────────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│  [⚡] │ CENTER: Active Synthesis & Streaming Verdict        │ RIGHT: Active Tools & Document Vault            │
│  [📊] │  - Frontier reasoning benchmark synthesis stream     │  - [x] Hybrid RAG Search (Neon pgvector)        │
│       │  - Line-level citation pills: [benchlm:L14-28]       │  - [ ] SQL Schema Audit                         │
│  [🛡️] │  - [Execute Plan] (#0a66c2) | [Approve Tool] (dark)  │                                                 │
│       ├──────────────────────────────────────────────────────┴─────────────────────────────────────────────────┤
│       │ BOTTOM SECTION: Telemetry & Mesh Overview                                                              │
│       │  - TCP Throughput bar chart (Alerts: 52 Excellent | High 439 | Medium 146 | Low 2.3k)                  │
│       │  - Service Overview Table (From, To, Status, Current Rate kbps)                                        │
└───────┴────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Header & Control Strip

- **Branding**: Clean rounded blue tile with CPU icon and `NexusAgent` title.
- **Interval & Filter Pills**: Sub-toolbar filters (`Interval: last 5 min`, `Breakdown: Service > Zone`, `Service in: 3`).
- **Search & Actions**: Rounded search input, Quota pill badge, dark pill action button (`Load ▼`), and Nexus Blue primary CTA (`1-Click Guest`).

### 3.2 Vertical Left Icon Rail

- Compact 56px icon rail providing instant 1-click navigation between:
    - `Layers` (Active Overview Dashboard)
    - `Database` (Document Vault & RFC chunk inspection)
    - `Zap` (MCP Tools & Wire logs)
    - `Activity` (System Telemetry & Metrics)
    - `ShieldCheck` (OWASP Agentic Security Guard)

### 3.3 Topology & Central Execution Stream

- **Interactive Architecture Flow**: Node-based cluster map with clean status chips and routing metrics.
- **Synthesizer Thread**: Real-time verdict with clickable source citation pills (`[benchlm:L14-28]`, `[artificial_analysis:L42-60]`) that preview and jump to exact line ranges.

### 3.4 Telemetry & Service Mesh Overview

- **TCP Throughput Card**: Segmented vertical bar chart displaying categorized metrics (Alerts: 52 Excellent, High, Medium, Low).
- **Service Mesh Table**: Clear rows with checkboxes, service source/destination, status badges (`Alert`, `Warm`, `Healthy`), and transfer rates.

---

## 4. Typography & Visual Hierarchy

- **Headings (`Outfit`)**: Clean, geometric modern sans-serif for dashboard titles, section cards, and modal headers.
- **Body & Controls (`Instrument Sans`)**: Modern, crisp geometric typography tailored for small-text readability, UI controls, and dense technical tables.
- **Code & Citations (`JetBrains Mono`)**: Monospaced font with high legibility for metrics (`150 kbps`), wire logs, and citation badges.

---

## 5. Micro-Interactions & States

- **Subtle Elevation on Hover**: Cards and nodes smoothly elevate (`transition: all 0.15s ease-out`).
- **Citation Hover Preview**: Citation badges (`[benchlm:L14-28]`) display instant popovers with snippet line previews.
- **Tactile Switches**: Clean Nexus Blue toggles with smooth pill translation.
- **Zero Distracting Animations**: No pulsing neon glows, spinning gradient borders, or excessive animated banners.

---

## 6. WCAG 2.2 Level AAA Compliance Specifications

NexusAgent strictly adheres to the highest level of accessibility (**WCAG 2.2 Level AAA**):

1. **Contrast (Enhanced) — SC 1.4.6 (Level AAA)**:
    - All standard text maintains a minimum contrast ratio of **7:1** against adjacent backgrounds:
        - Deep slate text (`#0F172A`) on white: **17.9:1**
        - Secondary body text (`#334155`) on white: **9.5:1**
        - Muted label text (`#475569`) on white: **7.1:1**
        - Primary brand text (`#004182`) on white: **9.7:1**
        - Citation pills (`#004182` on `#E8F3FC`): **9.0:1**
        - Buttons (`#FFFFFF` on `#004EA1`): **7.4:1**
2. **Non-Text Contrast — SC 1.4.11 (Level AA & AAA)**:
    - Interactive UI components (switch tracks, input borders `#64748B`, button borders) maintain at least **3:1** contrast against adjacent backgrounds.
3. **Focus Appearance — SC 2.4.13 (Level AAA)**:
    - High-contrast 2px solid focus indicators (`outline: 2px solid #004182`) with 2px offset (`outline-offset: 2px`) guaranteed never to be obscured by adjacent content.
4. **Target Size (Enhanced) — SC 2.5.5 (Level AAA)**:
    - All pointer targets (buttons, switch toggles, inputs, dialog triggers) occupy a minimum bounding touch target of at least **44 by 44 CSS pixels**.
5. **Bypass Blocks — SC 2.4.1 (Level A & AAA)**:
    - Persistent keyboard skip-navigation link (`.skip-link`) allows assistive technology users to jump directly to `#main-canvas`.
6. **Accessible Semantic Landmarks & Live Regions**:
    - Structured HTML5 semantic hierarchy: `role="banner"`, `role="main"`, `<aside aria-label="...">`, `<nav aria-label="...">`.
    - Dynamic AI stream regions employ `aria-live="polite"` and `aria-atomic="true"` for respectful screen reader announcements.
