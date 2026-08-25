---
name: wty-readme-generator
description: Generate, rewrite, or normalize project README and concise changelog files in the user's concise Chinese documentation style, and keep matching English README output in sync. Use this skill whenever the user asks to write a new README, refactor existing project documentation, align README or changelog tone and structure, add or repair bilingual README files, or convert scattered usage notes into the user's preferred README format with bilingual cross-links and compact commented command examples.
---

# WTY README Generator

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

- Put versions in descending order, with one simple heading per version, for example `## v6 - 2026-08-16`.
- Use a flat numbered list under each version; avoid nested bullets and long subsections.
- Record the change directly: affected component + action + necessary parameter or interface. Omit rationale unless it changes how the result should be used.
- Keep each item to one compact sentence or line when possible. Group only tightly coupled edits.
- Use imperative technical wording, such as `Add ...`, `Change ...`, `Remove ...`, `Update ...`; Chinese entries should use `新增`、`修改`、`移除`、`更新`、`统一`等动词开头。
- Keep code identifiers and values inline with backticks, including task IDs, function names, paths, ranges, dimensions, and units.
- Do not turn a changelog entry into a design document: avoid equations, implementation walkthroughs, test narratives, and repeated explanations of the same interface.
- Mention validation only as a short result when it is release-relevant, for example `GPU smoke test passed` or `通过定向测试`.
- Preserve the existing language and numbering convention of the target changelog. Do not introduce bilingual sections unless explicitly requested.

When converting a verbose change description into this format, retain only:

1. What changed.
2. Where or which task it affects.
3. The parameter, interface, compatibility, or behavior needed to identify the change.

Drop motivation, alternatives, chronology, and low-level implementation details unless the user explicitly asks for them.

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
