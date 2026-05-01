---
name: python-docstring-standard
description: Standardize Python function docstrings to a team format with a short summary, optional second-paragraph logic notes, optional Args/Returns sections. Default coding style uses four-space indentation and an object-oriented design mindset. Use when adding or normalizing docstrings in Python files, including class methods and nested callback functions.
---

# Python Docstring Standard

## Mandatory Opening Block (for Python script files)
When editing a runnable Python script, the very beginning of the script text (typically module docstring/header) must include:
1. What the script does (core functionality).
2. A brief usage overview.
3. If invokable from CLI:
   - Minimal startup command.
   - Full startup command with configurable options explained (only when extra configurable parameters are needed).
4. Add a `Notes:` section for caveats, environment assumptions, or operational reminders when needed.
5. If the script has no additional configurable parameters beyond the minimal command, omit both `Full Command:` and `Options:`.

Recommended structure:
```python
"""<Script purpose in one sentence>.

Overview:
<Brief description of workflow and expected input/output>.

Quick Start:
    python path/to/script.py <required args>

Full Command:
    python path/to/script.py --arg1 ... --arg2 ...

Options:
    --arg1: <meaning>
    --arg2: <meaning>

Notes:
    <Important caveats or usage reminders>
"""
```

## Overview
Apply this skill when the user asks to add, rewrite, or normalize Python docstrings by team convention. Edit only documentation text and keep runtime behavior unchanged.

## Coding Defaults
- Use 4 spaces per indentation level in all Python code snippets and generated examples.
- Do not use tab characters for indentation.
- Prefer object-oriented decomposition when structure decisions are needed: model related state/behavior in classes, and keep method responsibilities focused.
- For class methods, describe both the method action and its role within the class responsibility.

## Required Format
Use triple double quotes (`"""`) for every function entry (`def`), including class methods and nested functions unless the user narrows scope.

Write docstrings in this order:
1. First paragraph: one brief sentence describing the function's functionality.
2. Second paragraph: if needed, describe invocation/build logic directly as normal prose.
3. `Args:` section only when the function has input parameters worth documenting.
4. `Returns:` section only when the function returns a meaningful value.

Use this template:
```python
"""A brief description of the function's functionality.

If necessary, include the calling/build logic here as normal second-paragraph prose. Do not use subheadings.

Args:
    arg1: Description for arg1.
    arg2: Description for arg2.

Returns:
    A description of the return value.
"""
```

## Strict Rules
- Write logic notes directly in the second paragraph.
- Omit `Args:` when there are no meaningful inputs.
- Omit `Returns:` for `None`-style procedures unless the user explicitly wants it documented.
- In script header blocks, omit `Full Command:` and `Options:` when no extra configurable parameters are required.
- Put operational cautions and assumptions under `Notes:` when applicable.
- Keep wording concise and concrete; avoid restating obvious type hints.
- Use exactly 4 spaces for indentation in Python code examples and edits; never use tabs.
- Prefer an object-oriented modeling approach by default unless the user explicitly asks for a different style.

## Editing Workflow
1. Find all target `def` entries in scope.
2. Add missing docstrings or normalize existing ones to the required format.
3. Preserve function signatures, decorators, and executable code.
4. Keep terminology consistent across related functions.
5. Run syntax validation after edits (`python -m py_compile ...`) when feasible.

## Output Expectations
When reporting results, summarize:
- Which files were updated.
- Whether syntax validation was run and passed.
