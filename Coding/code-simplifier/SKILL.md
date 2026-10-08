---
name: code-simplifier
description: Simplify and refine recently modified code for clarity, consistency, and maintainability while preserving exact behavior. Use when the user asks to simplify, clean up, refactor for readability, polish recently changed code, or review touched code for unnecessary complexity.
---

# Code Simplifier

## Purpose

Improve code clarity, consistency, and maintainability without changing behavior.

Use this skill to refine recently modified code unless the user explicitly asks for a broader scope. Preserve all existing features, outputs, APIs, side effects, and observable behavior.

## Core Rules

1. Preserve functionality.
   - Do not change what the code does.
   - Keep all original features, outputs, and behavior intact.
   - Treat behavior changes as bugs unless the user requested them.

2. Follow project standards.
   - Read and follow local guidance such as `AGENTS.md`, `CLAUDE.md`, README files, contribution docs, formatter configs, lint rules, and nearby code patterns.
   - Prefer the repository's established style over generic preferences.
   - Keep import order, naming, file layout, typing style, error handling, and component patterns consistent with the project.

3. Enhance clarity.
   - Reduce unnecessary complexity and nesting.
   - Remove redundant code and weak abstractions.
   - Improve variable, function, and component names when they make intent clearer.
   - Consolidate related logic when it improves readability.
   - Remove comments that only restate obvious code.
   - Avoid nested ternary operators; prefer `switch` statements or `if`/`else` chains for multiple conditions.
   - Choose explicit readable code over dense or overly compact code.

4. Avoid over-simplification.
   - Do not create clever one-liners that are harder to debug.
   - Do not combine unrelated concerns into a single function, module, or component.
   - Do not remove helpful abstractions that improve organization.
   - Do not prioritize fewer lines over maintainability.

5. Keep scope tight.
   - Focus on code touched in the current session or recently modified code.
   - Do not perform broad refactors unless the user asks for them.
   - Avoid unrelated formatting churn.

## Workflow

1. Identify the recently modified or user-specified code.
2. Inspect nearby conventions and project guidance before editing.
3. Look for unnecessary branching, duplication, awkward names, redundant abstractions, and unclear control flow.
4. Apply small behavior-preserving refinements.
5. Run focused tests, type checks, lint checks, or syntax validation when feasible.
6. Report only meaningful changes and any verification performed.

## Output Expectations

When reporting results:

- State which files were simplified.
- Mention whether behavior was intended to remain unchanged.
- Include verification commands and results when run.
- Call out any tests or checks that could not be run.

## Source

Adapted from Anthropic's `code-simplifier` Claude plugin agent:
https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md
