# Workbench Tokens, Surface Layering, and System Persistence

Synthesized from `Dammyjay93/interface-design` (`Precision & Density` direction) and `pbakaus/impeccable` (`operate.md` and `typeset.md`). Use these token structures when refactoring existing CSS/Tailwind/component styles so every panel, control, and label shares one coherent system.

## 1. Surface Elevation & Border Progression (Dark & Light Workbenches)

In dark operational consoles, drop shadows barely register and bright hex borders create "wireframe cage" fatigue. Commit to **subtle lightness steps + low-opacity RGBA hairlines**:

### Dark Workbench Reference Palette (Cool Slate / Neutral Zinc)

- `--bg-canvas`: `#0b0d10` (3D viewport, map canvas, or deepest workspace ground)
- `--bg-panel`: `#111418` (docked sidebars, inspector panes - shares hue with canvas)
- `--bg-elevated`: `#171b21` (tab headers, active toolbars, subtle group headers)
- `--bg-floating`: `#1e232b` (dropdowns, popovers, command palettes, tooltips - one clear step above parent)
- `--bg-inset`: `#090b0e` (text inputs, number fields, code paths - **darker** than `--bg-panel` to signal inset editability without heavy borders)
- `--border-subtle`: `rgba(255, 255, 255, 0.06)` (default row dividers, pane splits)
- `--border-default`: `rgba(255, 255, 255, 0.10)` (inputs at rest, secondary button outlines)
- `--border-strong`: `rgba(255, 255, 255, 0.18)` (hover states, active control edges)

### Light Technical Workbench Reference Palette

- `--bg-canvas`: `#f3f5f7`
- `--bg-panel`: `#ffffff`
- `--bg-elevated`: `#f8fafc`
- `--bg-floating`: `#ffffff` (paired with `0 4px 16px rgba(15, 23, 42, 0.08)` + `1px solid rgba(15, 23, 42, 0.08)`)
- `--bg-inset`: `#f1f5f9`
- `--border-subtle`: `rgba(15, 23, 42, 0.06)`
- `--border-default`: `rgba(15, 23, 42, 0.12)`

## 2. Semantic & Accent Color Budget (60 / 30 / 10 Rule)

~90% of a dense workbench should be neutral surfaces and text hierarchy; ~10% carries semantic meaning:

- **Single Primary Accent** (for example, crisp emerald `#10b981` or cobalt `#3b82f6`): Used **only** on the primary action button (`Start Monitoring`, `Start Recording`), active tab indicator (`2px` bar or crisp pill), and selected state tint (`rgba(accent, 0.12)` fill + `rgba(accent, 0.30)` 1px border, never 100% neon stroke on 14 inactive items).
- **Semantic Status Tokens**:

  - `success` / `online`: `#22c55e` (dot/badge for live stream active)
  - `warning` / `standby`: `#f59e0b` (waiting for sensor sync / unaligned)
  - `danger` / `recording-stop`: `#ef4444` (active recording pulse, stop/abort, dropped-packet alert `> 0`)
- **Derived Muted Text**: On tinted alert banners, derive text from the banner's hue rather than washing out with neutral `#888888` gray.

## 3. Four-Level Typography & Numeric Hierarchy

Avoid arbitrary font sizes (`10px`, `11.5px`, `13px`, `15px` scattered randomly). Use a **1.15-1.2 fixed product scale** where **weight and opacity** carry more hierarchy than size jumps:

- **Font Stacks**:

  - `--font-sans`: `'Inter'`, `-apple-system`, `BlinkMacSystemFont`, `'PingFang SC'`, `'Microsoft YaHei'`, `sans-serif`
  - `--font-mono`: `'JetBrains Mono'`, `'Geist Mono'`, `'SFMono-Regular'`, `Consolas`, `monospace`
- **Four Text Tiers**:

  - **Tier 1 - Primary (`--text-primary`, `rgba(255,255,255,0.92)`)**: Active values, input contents, pane titles, selected tab names (`500-600` weight).
  - **Tier 2 - Secondary (`--text-secondary`, `rgba(255,255,255,0.68)`)**: Field labels, unselected tabs, secondary button labels, table row names (`400-500` weight).
  - **Tier 3 - Tertiary / Meta (`--text-muted`, `rgba(255,255,255,0.50)`)**: Units (`Hz`, `GiB`, `ms`), column headers, path hints, keyboard shortcuts (`400` weight, `>= 11px`, `>= 4.5:1` contrast across panel and elevated surfaces).
  - **Tier 4 - Disabled (`--text-disabled`, `rgba(255,255,255,0.28)`)**: Unavailable controls or unmounted modules.
- **Role Sizing (Fixed px/rem, Never Fluid `clamp()` Inside Panes)**:

  - Hero Telemetry Metric (for example, free disk `146.7 GiB` or live throughput): `18px-20px` / `600` / `tabular-nums`
  - Pane Title: `14px-15px` / `600`
  - Section Header: `12px-13px` / `600`
  - Standard Control & Row Copy: `12px-13px` / `400-500`
  - Metadata, Units & Table Column Headers: `11px` / `500` (minimum readable floor; add `+0.01em` to `+0.02em` letter-spacing on dark backgrounds)

## 4. Spacing Grid & Consistent Control Geometry

Pick a **4px base unit** and restrict all padding, gaps, and heights to multiples:

- **Spacing Scale**: `4px` (tight inline icon-to-label gap), `8px` (compact control gap / row vertical pad), `12px` (panel horizontal padding / control group gap), `16px` (section separation), `24px` (major region break).
- **Heading Rhythm**: Always place **more space above a section header than below it** (for example, `margin-top: 16px; margin-bottom: 6px`) so headers visually bind to the controls they govern without needing a surrounding card border.
- **Standardized Control Heights (Pick One Density Tier and Lock It)**:

  - Dense Workbench Toolbar / Compact Input: `26px-28px` height, `0 8px` horizontal padding, `4px` border-radius.
  - Standard Panel Input / Select / Button: `30px-32px` height, `0 10px-12px` horizontal padding, `5px-6px` border-radius.
  - Icon-Only Action (collapse, detach, reset): `24px-28px` visual square (`>= 24px` hit area), `4px` radius.

## 5. Persistent Design System File (`DESIGN.md` / `.interface-design/system.md`)

Prefer reusing and updating the project's existing CSS variables, Tailwind theme config, or `DESIGN.md`. If no design spec exists yet, offer to write `.interface-design/system.md` so future sessions maintain identical measurements:

```markdown
# Design System

## Direction
Personality: Precision & Density (Operational Workbench)
Foundation: Cool dark slate (`color-scheme: dark`)
Depth: Subtle lightness shifts + low-opacity RGBA hairlines (no nested cards)

## Tokens
- Spacing base: 4px (`4, 8, 12, 16, 24`)
- Surfaces: canvas `#0b0d10` -> panel `#111418` -> elevated `#171b21` -> floating `#1e232b` (inset `#090b0e`)
- Borders: subtle `rgba(255,255,255,0.06)`, default `rgba(255,255,255,0.10)`
- Radii: controls `4px`, groups/popovers `6px`, modals `8px`
- Type: Sans + Mono (`tabular-nums` on all telemetry/counters; 11px floor)

## Component Patterns
- Primary CTA: `28px` h, `0 12px` pad, `4px` radius, solid accent
- Secondary / Ghost Action: `28px` h, subtle fill or transparent hover `rgba(255,255,255,0.06)`
- Telemetry Row: `28px-32px` h, flush `1px` bottom hairline, right-aligned `tabular-nums` values
```
