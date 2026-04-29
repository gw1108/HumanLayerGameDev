---
name: create_structure
description: Read a design document and work interactively with the user to define the implementation structure (phases and ordering). Saves the agreed structure to thoughts/shared/claude-code-structure/.
model: opus
---

# Create Structure

## Starting point

The parameter is a path to a design document (produced by `/create_design`). Read it fully before doing anything else.

## Steps

### 1. Read the design file

Read the specified file completely (no offsets or limits). Extract:
- The agreed design decisions
- Out-of-scope items
- Any open questions that must be addressed before structuring

If open questions exist, ask the user to resolve them before proceeding.

### 2. Propose an initial phase breakdown

Draft a concise outline — no implementation details yet, just what each phase accomplishes and why that ordering makes sense:

```
## Proposed Structure

1. [Phase name] — [what it accomplishes, ~effort]
2. [Phase name] — [what it accomplishes, ~effort]
3. [Phase name] — [what it accomplishes, ~effort]

Does this phasing make sense? Should any phases be merged, split, or reordered?
```

Wait for feedback before writing any details.

### 3. Iterate on structure

- Adjust phases based on user feedback.
- If the user questions whether a phase is feasible, spawn a **codebase-analyzer** or **codebase-pattern-finder** sub-agent to verify, then update the proposal.
- Repeat until the user approves the phase list and ordering.

### 4. Define success criteria per phase

For each approved phase, agree on how "done" is verified:

```
**Phase [N] — [Name]**
Automated: project compiles without errors
Manual:    [what requires human review or testing]
```

Keep manual criteria specific and observable.

### 5. Confirm the full structure

Show the complete structure and wait for explicit approval:

```
**Full Structure:**
[Phase list with success criteria]

Ready to save?
```

### 6. Save the structure

```
python create_thought.py claude-code-structure <file_name_description> <content> [ticket]
```

Where `<file_name_description>` is a short kebab-case label. Tell the user the saved path.

## Output file format

```markdown
# Structure: [Topic]

## Design Source
[Path to the design document this was derived from]

## Overview
[1–2 sentences: what this set of phases delivers]

## Phases

### Phase 1: [Name]
**Goal:** [what it accomplishes]
**Success Criteria:**
- Automated: project compiles without errors
- Manual: [specific observable behavior]

### Phase 2: [Name]
**Goal:** [what it accomplishes]
**Success Criteria:**
- Automated: project compiles without errors
- Manual: [specific observable behavior]

[... repeat for each phase ...]

## Out of Scope
[Copied from design doc; add any new exclusions identified during structuring]
```

## Notes

- Do not write implementation steps or code — that is for `/create_plan_greenunity`.
- The structure must be fully approved by the user before saving.
- Each phase must have at least one manual success criterion. Automated criterion is always "project compiles without errors."
