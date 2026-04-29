---
name: research_codebase
description: Research and document a codebase from a refined question file produced by /refine-research-question. Always invoked with a path to thoughts/shared/questions/YYYY-MM-DD-*.md.
model: opus
---

# Research Codebase

## Starting point

The parameter is a path to a refined question file under `thoughts/shared/questions/`. Read it fully — it contains the user's question and any files the user provided.

## Steps

### 1. Read the question file

Read the specified question file in full (no offsets or limits). Extract:
- The refined question
- Research areas and what to investigate in each
- Clarifications gathered
- Edge cases to address
- Any referenced files (read those fully too, before spawning sub-agents)

### 2. Spawn parallel sub-agents

Based on the research areas and edge cases in the question file, spawn parallel sub-agents:

**Codebase research:**
- **codebase-locator** — find where relevant files and components live
- **codebase-analyzer** — understand how specific code works
- **codebase-pattern-finder** — find examples of existing patterns

**Thoughts directory:**
- **thoughts-locator** — discover what documents exist about this topic under `thoughts/shared/`
- **thoughts-analyzer** — extract key insights from the most relevant documents found

**Web research** (only if the question file explicitly requests it):
- **web-search-researcher** — return links alongside findings; include those links in the final report

Start with locator agents to find what exists, then dispatch analyzer agents on the most promising findings. Run independent agents in parallel. Tell each agent what to look for — don't prescribe how to search. Instruct all agents to describe what exists without recommendations or critique.

### 3. Wait for all sub-agents, then synthesize

Wait for ALL sub-agents to complete before proceeding. Then:
- Compile all findings; treat live codebase findings as primary source of truth
- Use `thoughts/shared/` findings as supplementary historical context
- Connect findings across components and address each research area from the question file
- Explicitly check each edge case listed in the question file
- Note any areas that remain unresolved

### 4. Gather metadata

```bash
bash hack/spec_metadata.sh
```

### 5. Write the research document

Save the refined research document by running:

```
python create_thought.py research <file_name_description> <content> [ticket]
```
 
Where `<file_name_description>` is a short summary of the topic, `<content>` is the content of the output file (see format below), and `[ticket]` is the optional ticket if mentioned. Tell the user where it was saved.

## Output file format

```markdown
---
researcher: [from metadata]
topic: "[refined question topic]"
tags: [research, codebase, relevant-component-names]
status: complete
last_updated_by: [researcher name]
source_question: [path to the question file]
---

# Research: [Topic]

## Research Question
[Refined question from the question file]

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
[Each edge case from the question file with findings]

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
```

### 6. Add GitHub permalinks (if applicable)

```bash
git branch --show-current && git status
```

If on main/master or the commit is pushed, get repo info:

```bash
gh repo view --json owner,name
```

Replace local file references in the research document with permalinks: `https://github.com/{owner}/{repo}/blob/{commit}/{file}#L{line}`

### 7. Present findings

Give the user:
- A concise summary of what was found
- Path to the research document
- Any open questions

To continue with follow-up questions:
```
/iterate_research_codebase [research-doc-path]
```

## Notes

- All paths are under `thoughts/shared/`
- Document what IS — describe current state without recommendations, critique, or suggestions
- Keep the main agent focused on synthesis; sub-agents do the deep reading
- Always wait for all sub-agents before synthesizing (step 3 before step 4)
- Always gather metadata before writing the document (step 4 before step 5)
- Always read referenced files fully before spawning sub-agents (step 1)
