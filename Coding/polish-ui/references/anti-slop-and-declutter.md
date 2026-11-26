# Anti-Slop Patterns and High-Density Decluttering Recipes

Synthesized from `pbakaus/impeccable` (`craft-floor.md`, `distill.md`, `quieter.md`, `operate.md`) and `Dammyjay93/interface-design` (`design-deslop`). Apply these structural transformations when an existing console feels "too AI-generated" or visually chaotic.

## 1. Banned AI Slop Tells in Product & Console UI

Scan the codebase and remove these patterns on sight:

1. **Cards nested inside cards**: A bordered rounded card sitting inside another bordered card inside a docked panel. Unbox inner containers into flat sections divided by whitespace or a single `1px` hairline (`border-top: 1px solid var(--border-subtle)`).
2. **Full-saturation borders on inactive items**: Wrapping 10+ unselected list items or chips in bright green, cyan, or purple `1px solid` pills. Inactive items stay quiet and neutral; only active/recording/fault states earn color.
3. **Ghost cards**: Combining a `1px` solid border with a wide, blurry drop shadow on dark surfaces. Pick one elevation cue (hairline border OR shadow on floating overlays).
4. **Thick colored side-stripes**: `border-left: 3px solid ...` on every callout, card, or list row. Replace with a `6px` status dot or subtle tinted badge only on true alerts.
5. **Decorative uppercase monospace kickers/eyebrows**: Putting `SYSTEM TELEMETRY // 01` above a `Telemetry` heading. Delete the kicker and let the section title speak once.
6. **Gradient buttons, glowing neon shadows, and emoji icons**: Replace gradients with solid semantic fills, strip `box-shadow: 0 0 15px accent` glows, and replace emoji (`🚀`, `📡`, `⚙️`) with consistent `14px-16px` stroke SVG icons (`1.5px` stroke width).
7. **Identical two-column box splits where one column is just a toggle list**: Avoid side-by-side equal boxes inside a narrow `320px` sidebar when a unified checklist table with inline controls cuts width and scrolling in half.

## 2. Structural Refactoring Recipes for Console Panels

### Recipe A: Collapse Repeated Sub-Captions into a Single-Header Telemetry Table

- **Before (AI Clutter)**: A "Selected Streams (14)" card where every row renders two lines, paired beside a separate "Available Streams" box of 14 green-bordered pills:

  - Line 1: `Camera Feed` + `[ 30 ] Hz`
  - Line 2 (repeated 14 times!): `0 frames · actual 0.0 Hz · dropped 0`

- **After (Workbench Craft)**: Merge selection and rate monitoring into **one unified, compact table** inside the pane (or a compact filterable checklist):

  - **Sticky 1-line table header (`11px` muted)**: `[x] Stream` | `Limit (Hz)` | `Actual` | `Frames / Drop`
  - **Single-line `28px-30px` rows**: `[x] Camera Feed` | `[ 30 ]` | `0.0` | `0 / 0` (dim `0` values in `--text-muted`; highlight `Drop > 0` in `--danger`).
  - **Result**: Eliminates 14 duplicate boxes, deletes 42 redundant words (`frames`, `actual`, `Hz`, `dropped` repeated 14x), cuts vertical scrolling by ~55%, and makes non-zero anomalies pop immediately.

### Recipe B: Tame Inline Helper Prose & Long File Paths

- **Before (AI Clutter)**: Three stacked lines of tiny muted instructions permanently sitting below an input (`Name: dataset_{timestamp} (filled on start)` + `Saves all streams by default; set rate on right, 0 means raw rate, static channels save on change only.`), plus a raw wrapping path `/var/lib/telemetry/recordings/session-2026-01`.
- **After (Workbench Craft)**:

  - Render storage capacity as a clean inline bar with primary `146.7 GiB free` (`tabular-nums`) and secondary `/ 1,000 GiB`, placing the directory path on one truncated monospace row (`text-overflow: ellipsis` + copy/open icon + full path on hover `title`).
  - Keep `{timestamp}` preview concise inline only when dynamic, and move the static rule (`0 = raw rate; static channels record on change`) into a subtle `?` tooltip next to the `Limit (Hz)` column header.

### Recipe C: Deduplicate Empty & Waiting States in Viewports

- **Before (AI Clutter)**: Showing a bright yellow warning banner at the top of a canvas/3D viewport (`Waiting for live stream, pose sync & alignment; enable source in Settings`) AND repeating `Waiting for live stream & synced state` in the center of the canvas.
- **After (Workbench Craft)**: State a waiting/empty condition **once** in a calm, centered empty-state lockup inside the canvas: subtle status icon, primary status (`Waiting for live stream & synced state`), and a direct secondary action link or hint (`Enable source in Settings ->`), keeping the top viewport toolbar purely for view controls (`2D | 3D`, layer select, camera reset).

### Recipe D: Establish Clear Action & Property Hierarchy in Inspector Panes

- **Before (AI Clutter)**: Key-value readouts (`Device`, `Points`, `Alignment`), mode dropdowns, `Start`, `Stop`, `Save`, `Load`, and `Unload` all share similar dark-gray bordered boxes and equal visual weight.
- **After (Workbench Craft)**:

  - **Read-only status block**: Compact 2-column key-value list at the top (`12px` secondary label left, `12px` `tabular-nums` primary value or subtle status badge right, no boxes around values).
  - **Primary workflow bar**: Group mode selects cleanly above or beside a clear primary action (`Start` with solid or tinted accent) and a quiet disabled/secondary `Stop` button (which turns semantic red only while the job is running).
  - **Collapsible disclosure sections (`<details>` / accordion)**: Use clean `28px` section headers with `12px` chevrons (`Status`, `Parameters`, `Filters`, `Presets`), `12px` internal indent or flush alignment, and `16px` gap before the next section without wrapping each open accordion in a heavy border box.
