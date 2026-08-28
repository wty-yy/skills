---
name: wty-markdown-standards
description: Write and normalize concise Markdown documentation and changelogs in the user's preferred style, keep bilingual README files synchronized when requested, and apply the user's commit, rebase, and push conventions when requested.
---

# WTY Markdown Standards

## Output Style

- Prefer short, direct wording
- Prefer noun phrases and concise statements over conversational phrasing
- Use headings in a simple sequence:
  - short introduction
  - usage
  - implementation details or other details
- Put explanations for commands inside code blocks as shell comments when possible
- Keep prose compact; avoid long paragraphs
- Do not wrap Markdown prose to a fixed column width. Keep each sentence or paragraph on one continuous line; insert line breaks only when required by Markdown structure such as headings, lists, tables, blockquotes, code fences, or paragraph separation
- Prefer `该工具` / `该脚本` over conversational phrases like `这个工具`
- Avoid filler such as `最简单的...` unless the user explicitly asks for it
- Do not add background, motivation, design history, or validation details unless they are required to use or verify the documented interface
- Preserve project identifiers, task names, paths, parameter names, numeric values, and units exactly
- Prefer one fact or action per sentence; combine items only when they form one inseparable change

## Concise Changelog Style

Use this style when the source or target is a `CHANGELOG`, release note, commit summary, or version history. The goal is a compact, directly searchable version history rather than a design document.

Rules:

- Put versions in descending semantic-version order: the newest version must be at the top and older versions must follow, with one simple heading per version, for example `## v6 - 2026-08-16`.
- Use a flat numbered list under each version; avoid nested bullets and long subsections.
- Record the change directly: affected component + action + necessary parameter or interface. Omit rationale unless it changes how the result should be used.
- Keep each item to one compact sentence or line when possible. Group only tightly coupled edits.
- Use concise English imperative wording by default, such as `Add ...`, `Change ...`, `Remove ...`, `Update ...`; use Chinese changelog entries only when explicitly requested.
- Keep code identifiers and values inline with backticks, including task IDs, function names, paths, ranges, dimensions, and units.
- Do not turn a changelog entry into a design document: avoid equations, implementation walkthroughs, test narratives, and repeated explanations of the same interface.
- Mention validation only as a short result when it is release-relevant, for example `GPU smoke test passed` or `通过定向测试`.
- Preserve the existing language and numbering convention of the target changelog. Do not introduce bilingual sections unless explicitly requested.

When converting a verbose change description into this format, retain only:

1. What changed.
2. Where or which task it affects.
3. The parameter, interface, compatibility, or behavior needed to identify the change.

Drop motivation, alternatives, chronology, and low-level implementation details unless the user explicitly asks for them.

## Markdown and Git Workflow

Apply these rules when the user asks to normalize changelogs and commit the current changes:

- Write all `CHANGELOG` entries in English unless the user explicitly requests another language.
- Sort version headings by semantic version in descending order; put the newest version first and use the date only as secondary context.
- Use one heading per version. If several changes share a version, merge them under the same heading and continue the numbered list instead of creating duplicate headings.
- Keep the newest version at the top, followed by older versions; keep each entry as one compact technical sentence.
- Preserve identifiers, parameters, paths, dimensions, numeric values, and units in backticks where appropriate.
- Before committing, inspect `git status`, the current branch, the remote, and recent history; include the current intended changes without overwriting unrelated user edits.
- If the commit defines a version, use only `v<version>` as the commit message, optionally followed by a component or task version with `+`, for example `v1.1`, `v1.1+climb1.1`, or `v1.1+climb1.2`.
- Do not append action descriptions, semicolons, or colons to a versioned commit message; use the `+<component><version>` suffix for task-level minor versions such as `climb1.1` and `climb1.2`.
- Before pushing, fetch or otherwise inspect the current `origin/<branch>` and rebase the local commit onto the latest remote branch.
- Resolve rebase conflicts by preserving both the remote changes and the local requested changes; re-check version ordering and duplicate headings after conflict resolution.
- Run `git diff --check` and relevant syntax or focused tests before pushing. Confirm the working tree and branch tracking state afterward.
- Use a normal push when history is unchanged. If the requested rebase rewrites a commit already pushed to the same branch, use `git push --force-with-lease`, never an unconditional `--force`.
- If a push is blocked only because the local Git LFS hook cannot run, report it and bypass the hook with `--no-verify` only after confirming that the commit does not add or modify LFS assets.

## Content Selection

- Treat emphasis in the prompt as implementation guidance, not automatic README content
- Include stable facts needed to build, run, configure, or understand the project interface
- Omit rejected alternatives, prior behavior, correction history, and implementation negotiation
- Avoid negative compliance statements unless the negative behavior is an operational constraint users must know
- Prefer showing the current command, path, or behavior instead of explaining what is not generated or supported
- Before finishing, remove sentences whose only purpose is to reassure the user that the prompt was followed

## Bilingual Requirements

When generating README files for this user:

- Default to producing both `README.zh-CN.md` and `README.md` unless the user limits scope
- Treat `README.zh-CN.md` and `README.md` as the standard bilingual filenames for this user's projects
- If only one language exists, treat it as the source of truth unless the user says otherwise
- If Chinese and English README files both exist but have drifted, resynchronize section order and coverage before polishing wording
- Add cross-links near the top:
  - Chinese README should link to `README.md`
  - English README should link to `README.zh-CN.md`
- Keep section order aligned across both languages
- Translate meaning, not wording literally; preserve the concise tone
- If the user asks for Chinese-only or English-only output, follow that scope and skip the missing language

## Centered Bilingual README Header

For a new public or project-facing bilingual README, use the [centered bilingual header template](references/centered-bilingual-readme-header.md) when the title style is unspecified or the user asks to restyle it.

- Keep YAML frontmatter before the centered HTML header.
- Include the project title, one compact repository summary, and links to both README languages.
- Emphasize the current language with `<strong>` and render the other language as a link.
- Keep the title, summary, links, and language order equivalent in `README.md` and `README.zh-CN.md`.
- Preserve an established title style unless the user requests this header format.

## Workflow

1. Inspect the current README files and the surrounding scripts or package files
2. Determine the source material:
   - existing Chinese README if present
   - otherwise existing English README
   - otherwise nearby scripts, package manifests, and docs
3. Mirror the user's Chinese structure first when bilingual output is required
4. Generate or update the paired English README to match the Chinese version section-by-section
5. Keep examples runnable and keep explanations inside code blocks as shell comments when possible
6. Separate durable project documentation from transient prompt rationale and discarded approaches
7. Before finishing, check that both languages mention the same commands, paths, defaults, and constraints
8. If a style baseline is needed:
   - read `references/docker-openclaw-README.zh-CN.md` for Chinese structure and tone
   - read `references/docker-openclaw-README.md` for matching English phrasing and section alignment
   - follow their section order and information flow:
     - short intro
     - concrete file or feature summary
     - usage commands
     - implementation or operational details
     - compact extra notes
9. For a new or restyled centered bilingual title, read [references/centered-bilingual-readme-header.md](references/centered-bilingual-readme-header.md) and replace every placeholder.

## Structure Guidance

Prefer structures like:

- intro
- feature summary or file list
- defaults if relevant
- table of contents only when the document is genuinely long
- usage
- implementation details
- other details

For tool READMEs, prefer:

- intro
- usage
- implementation details
- other details

## Editing Guidance

- Use `README.zh-CN.md` and `README.md` unless the user explicitly limits scope to a single language
- Preserve project-specific commands and paths
- Do not add extra marketing language
- Do not restate prompt corrections or rejected implementation choices as project documentation
- Keep code examples short and annotated with shell comments
- For README prose, prefer compact paragraphs and short lists; for changelogs, use the flat numbered format above instead of README-style explanations
- If Chinese and English READMEs already exist, keep them synchronized
- If repository facts are unclear, inspect code and scripts before drafting text
- Prefer filling obvious missing operational details over inventing product-level claims
- In the final response, state which README files were created or updated and whether bilingual sync was preserved
