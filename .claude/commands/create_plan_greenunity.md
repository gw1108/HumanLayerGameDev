---
name: create_plan_greenunity
description: Read a design document and write an actionable implementation plan with code-level steps. Saves the plan to thoughts/shared/plans/.
model: sonnet
---

# Create Plan

## Starting point

The parameter is a path to a design document (produced by `/create_design`). Read it fully before doing anything else.

## Steps

### 1. Read the design file

Read the specified file completely (no offsets or limits). Extract:
- The agreed design decisions
- Out-of-scope items
- Any open questions

If open questions remain, stop and ask the user to resolve them before proceeding.

### 2. Decide phases

Decompose the work into phases — do not ask the user to iterate on the phase structure. Each phase should be a thin vertical slice that compiles. For each phase, decide:
- Phase name
- Goal (one sentence)

Keep the phase list tight; merge anything that does not stand alone.

### 3. Research implementation details

For each phase, spawn parallel sub-agents to gather the specific file paths and code patterns needed:

- **codebase-locator** — find the exact files that need changing
- **codebase-pattern-finder** — find existing patterns to model the new code after
- **codebase-analyzer** — understand the current implementation at the specific spots that change

Wait for all sub-agents to complete before writing the plan.

### 4. Write the plan

Saving is a two-step process to avoid shell-quoting bugs with large markdown content:

**Step 1** — get the target path by running:

```
python "$(git rev-parse --show-toplevel)/create_thought.py" plans <file_name_description> [ticket]
```

The `$(git rev-parse --show-toplevel)` resolves to the repo root with forward slashes, so the command works from any subdirectory and avoids Bash interpreting backslashes in a Windows path as escape characters.

Where `<file_name_description>` is a short kebab-case label, and `[ticket]` is optional. The script prints the absolute path to stdout (and creates the parent directory). It does NOT write the file.

**Step 2** — use the `Write` tool directly to write the plan content (formatted per the template below) to that printed path.

Do not pause to summarize the plan or ask for confirmation before saving.

### 5. Report the export

After writing, your entire reply to the user is the single line:

```
I have exported your plan into [FULL_FILE_PATH]
```

Replace `[FULL_FILE_PATH]` with the absolute path printed by `create_thought.py`. Do not summarize phases, list steps, or solicit review.

## Plan template

````markdown
# [Feature/Task Name] Implementation Plan

## Overview
[1–2 sentences: what this plan delivers and why]

## Source Documents
- Design: [path to design doc]

## Current State
[What exists now, key constraints — with file:line references]

## Desired End State
[Specification of the final state]

## What We Are NOT Doing
[Explicit out-of-scope list]

---

## Phase 1: [Name]

### Goal
[What this phase accomplishes]

### Changes

#### [Component / File Group]
**File:** `path/to/file.ext`
**Change:** [summary]

```language
// specific code to add or modify
```

### Automated Verification
- [ ] Project compiles without errors
- [ ] [other automated check]

---

## Phase 2: [Name]

[same structure — Goal, Changes, Automated Verification only]

---

## Manual Verification (run after ALL phases are complete)

- [ ] [Specific UI or behavior check covering Phase 1]
- [ ] [Specific UI or behavior check covering Phase 2]
- [ ] [End-to-end behavior matching the design's success criteria]

## Manual Testing Steps
1. [step]
2. [step]

## References
- Original ticket: [path or link]
- Research: [path]
- Related patterns: [file:line]
````
