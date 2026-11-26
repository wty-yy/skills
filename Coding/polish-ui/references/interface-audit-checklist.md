# Web Interface Engineering & Polish Audit Checklist

Synthesized from `vercel-labs/agent-skills` (`web-design-guidelines` / Vercel Web Interface Guidelines) and `pbakaus/impeccable` (`audit.md` and `polish.md`). Run every item below before completing a UI polish pass or outputting a code review.

## 1. Numeric Stability, Typography & Copy Hygiene

- [ ] **Tabular numbers (`tabular-nums`)**: Every counter, Hz rate, duration (`0.0 s`), storage metric (`0.00 MiB`), coordinate, badge count, and table number sets `font-variant-numeric: tabular-nums` (or uses `--font-mono`) so live updates never cause horizontal jitter.
- [ ] **No-wrap on unit pairs**: Keep numbers glued to their units (`white-space: nowrap` or non-breaking space on `30 Hz`, `146.71 GiB`, `0.0 ms`) so values never orphan a unit onto a new line.
- [ ] **No hover weight shift**: Never change `font-weight` on `:hover` or `:active` (for example, `400 -> 600`), which shifts button or tab width; change color/background opacity instead, or reserve width.
- [ ] **Font smoothing & legibility floor**: Set `-webkit-font-smoothing: antialiased` on dark UI roots, avoid font weights `< 400`, and keep metadata `>= 11px` with APCA / WCAG `>= 4.5:1` contrast for readable text.
- [ ] **Consistent action naming**: Use concise, parallel verb/noun labels (`Start Recording` / `Stop & Save`, `Load Map` / `Unload`) in consistent casing (Sentence case or standard Chinese UI phrasing without trailing periods).

## 2. Dockable Layout, Alignment & Overflow Discipline

- [ ] **Single scroll container per pane**: Each docked sidebar/panel has one vertical scroll region (`overflow-y: auto; overscroll-behavior: contain`) while its tab bar and critical footer/action bar stay pinned (`flex-shrink: 0`). Eliminate nested double-scrollbars unless a bounded list exceeds `300px` inside a multi-section pane.
- [ ] **Theme-matched native browser chrome**: Set `color-scheme: dark` (or `light`) on `:root` / `<html>` so native scrollbars, number steppers, and Windows/Linux `<select>` menus do not flash bright white on dark consoles.
- [ ] **Unclipped overlays in docked panes**: Dropdown menus, tooltips, and popovers inside `overflow: hidden` or `overflow: auto` dock containers use portals, `<dialog>`, the Popover API, or `position: fixed` so pane edges never clip them.
- [ ] **Concentric radii & optical alignment**: Inner control radius `<=` outer container radius; side-by-side inputs and buttons share identical pixel height (for example, `28px` input beside `28px` button) and aligned baselines (`±1px` optical centering on icons).
- [ ] **Resilient truncation**: Long paths, stream/topic IDs, and artifact filenames use `min-width: 0` inside flex/grid children plus `overflow: hidden; text-overflow: ellipsis; white-space: nowrap`, exposing the full string via `title` or copy-on-click.

## 3. Controls, Forms, States & Accessibility

- [ ] **Generous hit targets (`>= 24px`)**: Compact panel icons (close, maximize, collapse chevron, help `?`, splitter grab area) maintain at least a `24px x 24px` clickable/draggable hit box even when the glyph is `14px`.
- [ ] **Zero dead zones on selection rows**: Clicking anywhere on a topic row or `<label>` toggles its checkbox/selection; never force users to click a tiny `12px` box accurately.
- [ ] **Visible `:focus-visible` rings**: Every `<button>`, `<input>`, `<select>`, tab, and accordion trigger shows a crisp keyboard focus ring (`:focus-visible`), never a bare `outline: none`.
- [ ] **Complete interactive states**: Every control defines `default`, `:hover` (increased contrast), `:active`, `:focus-visible`, `:disabled` (reduced opacity + `cursor: not-allowed`), and `loading` (spinner without changing button width).
- [ ] **Safe destructive / reset controls**: Actions like `Reset Layout`, `Delete`, or `Unload` do not share primary accent styling and confirm or allow safe recovery when data could be lost.
- [ ] **Redundant status encoding**: Sensor/connection states pair color with text or shape (`● Unaligned`, `● Recording`, `--` for no signal) rather than color alone.
- [ ] **Reduced motion respect**: Keep operational transitions snappy (`120ms-200ms ease-out`) and honor `@media (prefers-reduced-motion: reduce)` without removing state visibility.

## 4. Reporting Format (Audit Mode vs. Refactor Mode)

- **When asked to audit/review code without editing**: Report findings in terse, actionable lines grouped by severity (`P0` broken overflow/usability, `P1` hierarchy/slop/clutter, `P2` micro-polish):
  `path/to/Component.tsx:42 - [nested-cards] Remove inner .card border/background inside docked pane; use 1px top hairline.`
  `path/to/RecorderPanel.css:88 - [tabular-nums] Add font-variant-numeric: tabular-nums to .hz-readout to stop live layout jitter.`

- **When asked to beautify/edit UI code**: Apply the refactor directly in the target files, verify all existing props/callbacks remain wired, summarize the visual simplifications in 3 to 5 concise bullets, and update existing token docs (or offer to save `.interface-design/system.md` when no spec exists).
