---
name: coding-project-standards
description: Check and update project-level AGENTS.md with AI experiment and bulk data storage conventions. Use when the user asks to initialize or maintain these project standards; detect existing overlapping rules and flag them for review before adding requirements.
---

# Coding Project Standards

## Scope

Maintain the project root `AGENTS.md` with project-level rules for AI-run experiments and bulk data storage. Only inspect and edit standards files when running this skill; do not create experiment directories or move data. Do not impose additional naming or directory rules on production source code or formal tests.

## Language

Write new or updated standards in English by default, including the text added to `AGENTS.md`, unless the user explicitly requests another language. Preserve the language and content of unrelated existing sections.

## Review and Update Workflow

1. Identify the target project root and read its `AGENTS.md`. If the project already uses lowercase `agents.md`, keep using that file to avoid creating a duplicate with different capitalization.
2. Check the entire file for existing rules covering AI experiment directories, artifact categories, bulk data storage, size thresholds, or timestamp naming. Identify overlap by meaning, not just matching headings or directory names.
3. If related rules already exist, report their location and any overlap or conflicts with the standard below for the user to review. Do not automatically overwrite, merge, or append this set of rules. For partial coverage, also identify missing requirements; for complete and consistent coverage, explain that no duplicate addition is needed. If the user explicitly requests an update or translation of existing rules, make that requested change while preserving unrelated content.
4. If no related rules exist, append the standard text below and preserve all other content. If the file does not exist, create `AGENTS.md` in the project root with `# AGENTS.md` followed by the standard text.
5. Review the result to confirm that only the required standards were added or explicitly requested changes were made, without changing unrelated content.

## Standard Text to Insert

Insert the following section in English by default:

```markdown
## AI Experiment and Data Directory Standards

- All paths are relative to the project root.
- Use the current local time for timestamps in `YYYYMMDD_HHMMSS` format, for example `20261025_150710`.
- Store AI-run experiments in `debug_ai/<timestamp>_<experiment_name>/`. Use a short name describing the purpose, and reuse the same directory for follow-up work on that experiment.
- Within an experiment directory, store code in `src/`, images in `fig/`, videos in `vid/`, and data in `data/`. Create subdirectories as needed.
- If the cumulative size of an experiment or a collected data batch exceeds `100 MB`, move that batch to `debug_data/<timestamp>_<data_name>/`. Apply the threshold to the entire batch, not just individual files.
- Use a short name describing the data, and reuse the same directory for follow-up work on that batch. Save data directly there when it is known in advance that the threshold will be exceeded.
- When moving bulk data out of an experiment's `data/` directory, keep code, images, and videos in the original experiment directory. Avoid retaining duplicate data copies at the original location.
- After moving data, update affected script paths or configurations and verify that the experiment can still find its data.
- Add `/debug_ai/` and `/debug_data/` to the project root `.gitignore` to ignore both directories and their contents. Preserve existing rules, and do not add duplicates when equivalent rules already exist.
```

## Output Requirements

- After an update, report the standards file path and the requirements added or changed.
- When existing rules prevent an automatic addition, report their location and any overlap, conflicts, or missing requirements that need review, and state that no automatic changes were made.
