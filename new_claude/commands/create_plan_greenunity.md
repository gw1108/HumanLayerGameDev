---
name: create_plan_greenunity
description: Read a structure document and write a detailed, actionable implementation plan with code-level steps per phase. Saves the plan to thoughts/shared/plan/.
model: sonnet
---

# Create Plan

## Starting point

The parameter is a path to a structure document (produced by `/create_structure`). Read it fully before doing anything else.

## Steps

### 1. Read the structure file

Read the specified file completely (no offsets or limits). Extract:
- Phases and their goals
- Success criteria (automated and manual) for each phase
- Out-of-scope items
- The design source path — read that file too if you need to recall design decisions

### 2. Research implementation details

For each phase, spawn parallel sub-agents to gather the specific file paths and code patterns needed:

- **codebase-locator** — find the exact files that need changing
- **codebase-pattern-finder** — find existing patterns to model the new code after
- **codebase-analyzer** — understand the current implementation at the specific spots that change

Wait for all sub-agents to complete before writing the plan.

### 3. Write the plan

Save the plan using:

```
python create_thought.py plan <file_name_description> <content> [ticket]
```

Where `<file_name_description>` is a short label. The content must follow the template below exactly.

### 4. Present for review

Tell the user where the plan was saved, then ask:

```
Please review the plan and let me know:
- Are the per-phase steps specific enough to implement without guessing?
- Are the success criteria observable?
- Any missing edge cases or scope items?
```

### 5. Iterate until approved

Update the saved file based on feedback. Re-save with the same `create_thought.py` call (it will auto-version if the file exists). Continue until the user is satisfied.

## Plan template

````markdown
# [Feature/Task Name] Implementation Plan

## Overview
[1–2 sentences: what this plan delivers and why]

## Source Documents
- Design: [path to design doc]
- Structure: [path to structure doc]

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

### Success Criteria

#### Automated Verification
- [ ] Project compiles without errors

#### Manual Verification
- [ ] [Specific UI or behavior check]

**Pause here** for manual confirmation before proceeding to Phase 2.

---

## Phase 2: [Name]

[same structure...]

---

## Manual Testing Steps
1. [step]
2. [step]

## References
- Original ticket: [path or link]
- Research: [path]
- Related patterns: [file:line]
````

## Guidelines

- **No open questions in the final plan.** If you hit something unresolved, stop and ask the user before writing that section.
- **Every phase must have specific file paths** derived from sub-agent research — no generic placeholders.
- **Include a pause after each phase** for manual confirmation before the next phase begins.
