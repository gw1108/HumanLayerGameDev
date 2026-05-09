---
name: create_design
description: Read a research document and work interactively with the user to settle on a design approach. Saves the agreed design to thoughts/shared/claude-code-design/.
model: opus
---

# Create Design

## Starting point

The parameter is a path to a research document (produced by `/research-codebase`). Read it fully before doing anything else.

## Steps

### 1. Read the research file

Read the specified file completely (no offsets or limits). Extract:
- The problem being solved
- Current state of the codebase (files, patterns, constraints)
- Any open questions flagged by the researcher

Also read any files the research document references with `file:line` notation that are critical to understanding the problem.

### 2. Identify design axes

Based on the research, identify the key decisions that must be made before implementation can begin. For each axis present 2–3 concrete options, e.g.:

```
**Design Options:**

1. [Option A] — [what it does, trade-offs]
2. [Option B] — [what it does, trade-offs]
3. [Option C if applicable]

Which approach fits best?
```

Only ask about decisions that genuinely affect the implementation path. Do not present options that are equivalent in effort or outcome.

### 3. Iterate with the user

- Present one set of options at a time; wait for the user to choose before moving on.
- If the user's answer reveals a misunderstanding, spawn a **codebase-analyzer** or **codebase-locator** sub-agent to verify the facts, then re-present.
- Keep iterating until every major design axis is resolved.

### 4. Save the design

Once all design decisions are resolved through the iteration in step 3, save immediately. Do not pause to summarize the agreed design or ask for confirmation before saving — the iteration in step 3 is the agreement.

Saving is a two-step process to avoid shell-quoting bugs with large markdown content:

**Step 1** — get the target path by running:

```
python "$(git rev-parse --show-toplevel)/create_thought.py" claude-code-design <file_name_description> [ticket]
```

The `$(git rev-parse --show-toplevel)` resolves to the repo root with forward slashes, so the command works from any subdirectory and avoids Bash interpreting backslashes in a Windows path as escape characters.

Where `<file_name_description>` is a short kebab-case topic label, and `[ticket]` is optional. The script prints the absolute path to stdout (and creates the parent directory). It does NOT write the file.

**Step 2** — use the `Write` tool directly to write the content (formatted per the template below) to that printed path.

After writing, your entire reply to the user is the single line:

```
I have exported your design into [FULL_FILE_PATH]
```

Replace `[FULL_FILE_PATH]` with the absolute path printed by `create_thought.py`. Do not summarize the design, list decisions, or add any other content.

## Output file format

```markdown
# Design: [Topic]

## Problem Statement
[One paragraph: what we are solving and why]

## Research Source
[Path to the research document this was derived from]

## Design Decisions

### [Axis 1]
**Choice:** [chosen option]
**Rationale:** [why this was chosen over alternatives]

### [Axis 2]
**Choice:** [chosen option]
**Rationale:** [why]

## Out of Scope
[Explicit list of things we are NOT doing]

## Open Questions
[Anything that still needs clarification before a plan can be written]
```

## Notes

- Do not write a plan or list implementation steps — that is for `/create_plan_greenunity`.
- Stay skeptical: if a design choice seems to contradict what the research found, say so.
- All decisions must be resolved before saving. Do not save a design with unresolved questions.
