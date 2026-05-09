---
name: research_codebase_skip
description: Research and document a codebase directly from a question provided as the parameter, skipping the refinement step. Invoked with the user's question as a string.
model: opus
---

# Research Codebase (Skip Refinement)

## Starting point

The parameter is the user's question as a string. Use it directly as the research question.

## Steps

### 1. Parse the question

Read the parameter as the research question. Extract:
- The core question being asked
- Any files, paths, or components the user explicitly referenced (read those fully before spawning sub-agents)
- Implicit research areas suggested by the question
- Likely edge cases worth addressing

If the question is ambiguous, make reasonable assumptions and note them in the final report rather than blocking on clarification.

### 2. Spawn parallel sub-agents

Based on the inferred research areas and edge cases, spawn parallel sub-agents:

**Codebase research:**
- **codebase-locator** — find where relevant files and components live
- **codebase-analyzer** — understand how specific code works
- **codebase-pattern-finder** — find examples of existing patterns

**Thoughts directory:**
- **thoughts-locator** — discover what documents exist about this topic under `thoughts/shared/`
- **thoughts-analyzer** — extract key insights from the most relevant documents found

**Web research** (only if the question explicitly requests it):
- **web-search-researcher** — return links alongside findings; include those links in the final report

Start with locator agents to find what exists, then dispatch analyzer agents on the most promising findings. Run independent agents in parallel. Tell each agent what to look for — don't prescribe how to search. Instruct all agents to describe what exists without recommendations or critique.

### 3. Wait for all sub-agents, then synthesize

Wait for ALL sub-agents to complete before proceeding. Then:
- Compile all findings; treat live codebase findings as primary source of truth
- Use `thoughts/shared/` findings as supplementary historical context
- Connect findings across components and address each inferred research area
- Explicitly check the edge cases you identified
- Note any areas that remain unresolved

### 4. Write the research document

Saving is a two-step process to avoid shell-quoting bugs with large markdown content:

**Step 1** — get the target path by running:

```
python "$(git rev-parse --show-toplevel)/create_thought.py" research <file_name_description> [ticket]
```

The `$(git rev-parse --show-toplevel)` resolves to the repo root with forward slashes, so the command works from any subdirectory and avoids Bash interpreting backslashes in a Windows path as escape characters.

Where `<file_name_description>` is a short kebab-case summary of the topic, and `[ticket]` is the optional ticket if mentioned. The script prints the absolute path to stdout (and creates the parent directory). It does NOT write the file.

**Step 2** — use the `Write` tool directly to write the content (formatted per the template below) to that printed path.

Do not pause to summarize the findings or ask for confirmation before saving.

## Output file format

```markdown
---
topic: "[question topic]"
tags: [research, codebase, relevant-component-names]
status: complete
source_question: [verbatim question from the parameter]
---

# Research: [Topic]

## Research Question
[The question as provided by the user]

## Summary
[High-level description of what was found]

## Detailed Findings

### [Research Area 1]
- What exists (`file.ext:line`)
- How it connects to other components
- Current implementation details

### [Research Area 2]
...

## Edge Cases Addressed
[Each edge case considered with findings]

## Code References
- `path/to/file.py:123` — description
- `another/file.ts:45-67` — description

## Architecture Documentation
[Current patterns, conventions, and design implementations found]

## Historical Context (from thoughts/shared/)
[Relevant insights with references]
- `thoughts/shared/something.md` — description

## Related Research
[Links to other documents in thoughts/shared/research/]

## Open Questions
[Anything that needs further investigation]

## Assumptions Made
[Any assumptions made about the question's intent, since refinement was skipped]
```

### 5. Report the export

After writing, your entire reply to the user is the single line:

```
I have exported your research into [FULL_FILE_PATH]
```

Replace `[FULL_FILE_PATH]` with the absolute path printed by `create_thought.py`. Do not summarize findings, list assumptions, list open questions, or add follow-up instructions — assumptions and open questions belong inside the document itself, and the user can run `/iterate_research_codebase [research-doc-path]` if they want follow-ups.

## Notes

- All paths are under `thoughts/shared/`
- Document what IS — describe current state without recommendations, critique, or suggestions
- Keep the main agent focused on synthesis; sub-agents do the deep reading
- Always wait for all sub-agents before synthesizing (step 3 before step 4)
- Always read explicitly referenced files fully before spawning sub-agents (step 1)
- Since the refinement step is skipped, surface any assumptions you made in the final report so the user can correct course on follow-up
