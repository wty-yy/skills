---
name: wty-markdown-standards
description: Write and normalize concise Markdown documentation and changelogs in the user's preferred style, and keep bilingual README files (`README.md` and `README.zh-CN.md`) synchronized when requested.
---

# WTY Markdown Standards

## Scope

- Modify README files or `AGENTS.md` only when the user explicitly requests edits to those files; code changes alone do not authorize documentation updates.
- Include algorithm or environment implementation details in README files or `AGENTS.md` only when explicitly requested.
- For Git commit, squash, rebase, and push rules (including versioned release commits), use `git-version-workflow`.

## Style and Content Selection

- Prefer short, direct wording, noun phrases, and compact paragraphs over conversational phrasing or marketing language.
- Prefer one fact or action per sentence; combine items only when they form one inseparable change.
- Do not wrap Markdown prose to a fixed column width. Keep each sentence or paragraph on one continuous line; insert line breaks only where Markdown structure requires them (headings, lists, tables, blockquotes, code fences, paragraph breaks).
- In Chinese docs, prefer `该工具` / `该脚本` / `该目录` over conversational phrases like `这个工具` / `这个目录`; avoid filler such as `最简单的...` unless requested.
- Include stable facts needed to build, run, configure, or understand the interface. Inspect nearby code and scripts before drafting when repository facts are unclear; prefer filling missing operational details over inventing product-level claims.
- Preserve project identifiers, task names, paths, parameter names, numeric values, and units verbatim.
- Keep commands runnable and place short explanations inside code blocks as shell comments when possible.
- Omit background, motivation, design history, rejected alternatives, prompt-negotiation history, negative compliance statements (unless they are operational constraints users must know), and sentences whose only purpose is to reassure the user that the prompt was followed.
- Keep skill instructions reusable across projects; store repo-specific task names, paths, and experiment policies in project guidelines.

## README Structure

- General READMEs: short intro → feature summary or file list → defaults (if relevant) → table of contents (only when genuinely long) → usage → implementation details → other details.
- Tool READMEs: short intro → usage → implementation details → other details.

## Bilingual READMEs

- Default to maintaining both `README.zh-CN.md` and `README.md` unless the user limits scope to one language.
- Source-of-truth priority: existing Chinese README → existing English README → nearby scripts, package manifests, and docs.
- Mirror the Chinese structure first when producing bilingual output, then align the English README section by section. If both files exist and have drifted, resynchronize section order and coverage before polishing wording.
- Add cross-links near the top (`README.zh-CN.md` links to `README.md` and vice versa).
- Translate meaning rather than wording literally, keeping the concise tone and ensuring both files list the same commands, paths, defaults, and constraints.
- Style baseline references (read when needed):
  - `references/docker-openclaw-README.zh-CN.md` (Chinese structure and tone)
  - `references/docker-openclaw-README.md` (English phrasing and section alignment)

### Centered Bilingual Header

For a new public or project-facing bilingual README, use [references/centered-bilingual-readme-header.md](references/centered-bilingual-readme-header.md) when the title style is unspecified or the user asks to restyle it. Preserve an established title style unless restyling is requested.

- Keep any existing YAML frontmatter before the centered HTML header.
- Include the project title, one compact summary, and links to both languages (`<strong>` for the current language, `<a>` for the other).
- Keep title, summary, links, and language order equivalent across `README.md` and `README.zh-CN.md`, and replace every placeholder.

## Concise Changelog Style

Apply when creating or normalizing a `CHANGELOG`, release note, or version history:

- Order version headings by semantic version descending (newest at the top), using one heading per version (for example, `## v6 - 2026-08-16`) with the date as secondary context. Merge multiple changes sharing a version under the same heading instead of creating duplicate headings.
- Use a flat numbered list under each version; avoid nested bullets and long subsections.
- Keep each entry to one compact technical sentence without a terminal period (use internal punctuation only when needed for readability). Group only tightly coupled edits.
- Write entries in concise English imperative wording by default (`Add ...`, `Change ...`, `Remove ...`, `Update ...`); preserve an existing target changelog's language and numbering convention unless requested otherwise, and do not introduce bilingual sections unless asked.
- Record only: (1) what changed, (2) affected component or task, and (3) parameters, interfaces, compatibility, or behavior needed to identify the change. Wrap identifiers, paths, ranges, dimensions, and units in backticks.
- Omit rationale, equations, implementation walkthroughs, training procedures, metrics, checkpoint selection, validation narratives, and repeated explanations. Store detailed experiments and debugging records in separate project docs.
- Version consolidation (only when explicitly requested): retain only requested version headings, move useful experiment history to separate project docs, and remove redundant superseded code after checking callers. Never discard version history during ordinary changelog edits.

## Output

In the final response, state which Markdown files were created or updated and whether bilingual synchronization was preserved.
