---
name: python-docstring-standard
description: Standardize Python script headers, class docstrings, and function docstrings using a concise team format (short summary, optional prose logic notes, optional Args/Returns/Raises sections, and 4-space indentation). Use when adding, rewriting, or normalizing docstrings in Python scripts and modules.
---

# Python Docstring Standard

## Scope

Apply this skill when adding, rewriting, or normalizing docstrings in Python scripts or library modules.

- During docstring-only passes, edit documentation text only and preserve function signatures, decorators, and runtime behavior.
- Use 4 spaces per indentation level in all Python edits and examples; never use tabs.
- When the user also asks to design or structure new Python code under this convention, prefer focused object-oriented classes to group related state and behavior; do not refactor existing code during a docstring-only pass.

## Module and Script Headers

### Runnable Python Scripts

Place a module docstring at the top of runnable CLI scripts (after any shebang or encoding line) with:

1. One-sentence summary of what the script does.
2. `Overview:` briefly describing workflow and expected inputs/outputs.
3. `Quick Start:` showing the minimal startup command (when CLI-invokable).
4. `Full Command:` and `Options:` only when the script accepts extra configurable parameters beyond the minimal command; omit both sections otherwise.
5. `Notes:` for operational caveats, environment assumptions, or reminders when needed.

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

### Non-Script Library Modules

Use a concise one-sentence summary (plus an optional second paragraph for module scope or caveats) without CLI command sections.

## Class and Function Docstrings

Use triple double quotes (`"""`) for classes, module-level functions, class methods, and non-trivial nested helpers. Skip trivial self-explanatory one-line nested callbacks or lambdas unless the user requests exhaustive coverage.

Write docstrings in this order:

1. **Summary line**: one brief, concrete sentence describing what the class or function does (for class methods, make its role within the class clear).
2. **Logic notes (optional)**: second paragraph written as plain prose without subheadings, explaining non-obvious invocation, state, or build logic.
3. **`Args:` (optional)**: include only when there are meaningful parameters worth documenting; avoid restating obvious type hints.
4. **`Returns:` (optional)**: include only when a meaningful value is returned; omit for `None`-returning procedures unless explicitly requested.
5. **`Raises:` (optional)**: include only when callers need to handle notable exceptions raised intentionally by the function.

```python
class ExampleRunner:
    """Manage configuration state and execute example tasks.

    Holds resolved runtime options and coordinates setup and cleanup per run.
    """

    def run(self, target: str, retries: int = 1) -> bool:
        """Execute the configured task against a target.

        Retries transient failures in order and stops on the first success.

        Args:
            target: Destination identifier to process.
            retries: Maximum execution attempts before failing.

        Returns:
            True if the task succeeded within the allowed attempts.

        Raises:
            ValueError: If target is empty or retries is less than 1.
        """
```

## Workflow and Verification

1. Identify the target Python files and docstring scope (script header, classes, functions).
2. Add missing docstrings or normalize existing ones to the template above while keeping terminology consistent across related symbols.
3. Preserve all executable code, signatures, and decorators.
4. Run syntax validation (`python3 -m py_compile <files>`) when feasible.
5. Report which files were updated and whether syntax validation passed.
