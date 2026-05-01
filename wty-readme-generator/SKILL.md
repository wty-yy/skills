---
name: wty-readme-generator
description: Generate, rewrite, or normalize project README files in the user's concise Chinese documentation style, and keep matching English README output in sync. Use this skill whenever the user asks to write a new README, refactor existing project documentation, align README tone or structure, add or repair bilingual README files, or convert scattered usage notes into the user's preferred README format with bilingual cross-links and compact commented command examples.
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
- Prefer `该工具` / `该脚本` over conversational phrases like `这个工具`
- Avoid filler such as `最简单的...` unless the user explicitly asks for it

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
6. Before finishing, check that both languages mention the same commands, paths, defaults, and constraints
7. If a style baseline is needed:
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
- table of contents if the document is more than a few sections
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
- Keep code examples short and annotated with shell comments
- If Chinese and English READMEs already exist, keep them synchronized
- If repository facts are unclear, inspect code and scripts before drafting text
- Prefer filling obvious missing operational details over inventing product-level claims
- In the final response, state which README files were created or updated and whether bilingual sync was preserved
