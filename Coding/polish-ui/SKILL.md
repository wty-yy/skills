---
name: polish-ui
description: Refine, de-slop, and systematize information-dense web interfaces, VS Code-style dockable consoles, dashboards, and developer tools without breaking existing features. Eliminates nested box-in-box cards, consolidates cluttered micro-text into tabular layouts, enforces 4px grid tokens and dark-mode surface hierarchy, and locks tabular-nums telemetry stability. Use when asked to beautify, polish, audit, or remove AI flavor from an existing web app, dashboard, console, or admin panel (including 网页美化, 界面优化, 控制台去AI味, 消除套娃框, 优化密集小字排版); do not use for marketing landing pages, brand showcases, native mobile apps, backend feature development, or prose/text de-AI editing.
---

# Polish UI

Transform functional but cluttered, AI-generated product interfaces into calm, high-craft operational workspaces inspired by Linear, VS Code, and Vercel. This skill combines token-driven workbench architecture, progressive structural decluttering and typographic distillation, and engineering-grade interaction hygiene while keeping 100% of existing features intact.

## When to Use

- Beautifying an existing VS Code-style dockable workbench, monitoring dashboard, telemetry/IoT console, admin panel, or developer tool whose features already work.
- Stripping recognizable "AI UI slop": cards nested inside cards, neon/high-saturation borders on inactive items, decorative uppercase eyebrows, gradient spam, and mismatched control heights.
- Cleaning up cluttered micro-text, multi-line inline instructions, and repetitive per-item status captions inside narrow sidebars or tool panels.
- Auditing frontend code (HTML, CSS, Tailwind, React, Vue, Svelte) for `tabular-nums` numeric stability, alignment, dark-mode contrast, hit targets, scrollbars, and focus states.
- Establishing or enforcing a consistent design token specification (via existing CSS variables, Tailwind theme, `DESIGN.md`, or `.interface-design/system.md`) so future UI edits never drift.

## Core Principles and Rule Precedence

Operational tools succeed through earned familiarity and invisible structure, not marketing drama:

1. **Zero functional regression**: Preserve every existing event handler, data binding, WebSocket/telemetry field, form control, keyboard shortcut, and drag/dock resize behavior. Refactor visual wrappers, CSS tokens, and layout density without deleting capabilities.
2. **Operate mode over landing-page theatrics**: Dense tools are for sustained work, not persuasion. Never introduce giant hero banners, serif display fonts, `clamp()` fluid headings that shrink unpredictably inside sidebars, or decorative page-load animations.
3. **Unbox before decorating**: When a dockable pane or split view already bounds a region, inner cards-in-cards are visual noise. Group related fields with whitespace (`more space above a heading than below it`), subtle surface lightness shifts, or a single `1px` low-opacity hairline before reaching for a box.
4. **Hierarchy through weight, opacity, and tabular alignment**: Fix cluttered small text by removing redundant repeated labels and separating roles via weight + tone (`600` primary value, `500` secondary label, `400` muted metadata) rather than shrinking captions into unreadable sub-11px text.

## Steps

1. **Inventory functional contracts and load or define system tokens**: Inspect the target code (and any user screenshot) to catalog every interactive control, live data readout, and panel boundary that must keep working. Reuse existing project tokens first (CSS custom properties, Tailwind theme config, `DESIGN.md`, or `.interface-design/system.md`); otherwise establish a compact workbench token set on a **4px base grid** (`4, 8, 12, 16, 24, 32`) with one committed depth strategy (`Borders-only` + subtle lightness elevation; see `references/workbench-tokens-and-surfaces.md`).
2. **Unbox nested containers**: Flatten multi-layer card nesting inside panels (detailed before/after patterns in `references/anti-slop-and-declutter.md`):

   - Replace `Panel -> Outer Card -> Inner Bordered Group -> Bordered Item Pill` with `Panel -> Section Header + 1px Hairline -> Flush List or Compact Table`.
   - Use low-opacity borders (`rgba(255, 255, 255, 0.06)` to `0.10` in dark mode; `rgba(0, 0, 0, 0.08)` in light mode) instead of harsh solid hex borders.
   - Style text/number inputs slightly **darker (inset)** than their parent panel in dark mode so they signal editability without heavy outlines.
   - Keep nested border radii concentric (`child_radius <= parent_radius`, typically `4px` controls inside `6px` groups).
3. **Consolidate micro-text clutter and tighten typography**: Eliminate repetitive sub-captions and inline prose walls:

   - **Tabularize repeated metrics**: When N list rows each repeat the same secondary caption (`0 frames · actual 0.0 Hz · dropped 0`), convert the list into a compact aligned grid/table where column headers (`Target Hz`, `Actual`, `Frames / Drop`) appear **once** at the top and rows hold clean values.
   - **Compress verbose helper prose**: Shorten multi-line instructional paragraphs under inputs into a crisp 1-line hint or move edge-case rules into a `?` info popover/tooltip.
   - **Enforce a 4-tier fixed rem/px type ramp**: Use one clean UI sans plus one monospace family (`1.125` to `1.2` scale: `11px` metadata floor, `12px-13px` compact labels/controls and section headers, `14px` primary values, `14px-15px` pane titles). Compensate light-on-dark text with `1.4-1.5` line-height, subtle positive tracking on `11px` labels, and weights `>= 400`.
4. **Quiet visual noise and sharpen action hierarchy (60/30/10 budget)**: Reserve high-chroma color strictly for meaning:

   - Strip bright green/blue/amber full borders from inactive selectable chips or list items; represent unselected items with neutral subtle fills or plain rows, and active selection with a low-alpha accent tint (`10%-15%` opacity) plus crisp foreground text or a compact checkbox/toggle.
   - Enforce a 3-tier button ladder per view: at most **one solid accent Primary CTA** (`Start Recording`, `Connect`), subtle surface-filled **Secondary buttons**, and borderless **Ghost toolbar controls** (`Reset Layout`, `Reset View`). Keep destructive/stop actions distinct (`danger` token only when active or confirming).
5. **Harden live telemetry, controls, and browser surfaces**: Apply the engineering checks in `references/interface-audit-checklist.md`:

   - Apply `font-variant-numeric: tabular-nums` and `white-space: nowrap` to every live counter, frequency, timer, byte size, coordinate, and status badge so changing digits never jitter adjacent labels.
   - Truncate long filesystem paths or stream/topic IDs cleanly (`text-overflow: ellipsis`, `overflow: hidden`, with full path in `title` or copy button).
   - Set `color-scheme: dark` (or `light`) on `<html>` so native scrollbars and `<select>` menus match the theme; ensure only one clean scroll container per pane (no nested double-scrollbars) and render dropdowns/popovers via portals or `fixed` positioning so `overflow: auto` panes never clip them.
   - Guarantee `>= 24px` hit targets on compact icon buttons, zero dead zones between checkboxes and labels, no font-weight changes on `:hover` that shift width, and clear `:focus-visible` rings.
6. **Verify with the Squint Test and persist tokens optionally**: Blur-check the hierarchy (primary canvas/viewport -> primary pane action -> active telemetry -> quiet chrome). Confirm zero functional props/handlers were lost. If asked for a code review only, output findings in terse `file:line - issue -> fix` format; when editing code, apply changes cleanly and update existing token docs (or offer to save `.interface-design/system.md` if no spec exists and the user wants one).

## Gotchas

- **Never sacrifice operator speed for minimalism**: Hiding critical telemetry or primary stop/record controls inside extra menus hurts usability. Decluttering removes *redundant labels and wrapper borders*, never real operational controls or live status signals.
- **Do not rely on color alone for hardware/system status**: Pair status dots (online, warning, unaligned, recording) with explicit short state text (`Unaligned`, `0.0 Hz`, `Recording`) so color-blind operators and squinted peripheral vision both read state accurately.
- **Keep dockable splitters and 3D/canvas viewports fluid**: Never put fixed pixel widths or large outer margins around central WebGL/canvas/map viewports in a dockable workbench; let the viewport claim maximum space while sidebars stay compact (`260px-340px` typical default) and internally scrollable.
- **Avoid ghost cards and decorative tech costumes**: Never combine a `1px` border with a wide drop shadow on dark panels, never add `>1px` colored left/right stripes to every row, and never use monospace for decorative uppercase section kickers (reserve monospace for paths, IDs, code, and live numbers).
