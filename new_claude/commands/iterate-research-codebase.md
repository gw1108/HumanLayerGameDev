---
name: iterate_research_codebase
description: Handle follow-up questions on an existing research document produced by /research_codebase. Invoked with the research doc path.
model: opus
---

# Iterate Research Codebase

## Starting point

Invoked with one path: the full research document (e.g., `thoughts/shared/research/2026-04-29-auth-flow.md`).

Read the research document fully — no offsets or limits.

If the user hasn't provided a follow-up question yet, ask:

```
I've loaded the research context. What's your follow-up question?
```

## Steps

### 1. Read the research document

Read the full research document. Both in full.

### 2. Understand the follow-up question

Identify what's new territory vs. what the prior research already covered. If the question touches something already addressed, note it and either confirm or extend the prior finding rather than re-running the same research.

### 3. Spawn targeted sub-agents

Spawn only the agents needed for the follow-up — don't repeat the original research:

- **codebase-locator** / **codebase-analyzer** / **codebase-pattern-finder** — for codebase questions
- **thoughts-locator** / **thoughts-analyzer** — for historical or design context
- **web-search-researcher** — only if explicitly needed

Run independent agents in parallel. Instruct all agents to describe what exists without recommendations or critique.

### 4. Wait for all sub-agents, then synthesize

Wait for ALL sub-agents to complete. Combine new findings with prior context from the research document.

### 5. Append to the research document

Add a new section to the existing document:

```markdown
## Follow-up Research [YYYY-MM-DD HH:MM timezone]

**Question**: [follow-up question]

### Findings
[New findings with file paths and line numbers]

### Code References
- `path/to/file.py:123` — description
```

Update frontmatter:
```yaml
last_updated: YYYY-MM-DD
last_updated_by: [researcher]
last_updated_note: "Follow-up: [brief description]"
```

### 6. Present findings

Give the user:
- A concise answer to their follow-up question
- What was new vs. already covered in the prior research
- Any new open questions

To continue with another follow-up:
```
/iterate_research_codebase [research-doc-path]
```

## Notes

- The research document is the source of truth for what was already investigated — trust it
- Only research what's genuinely new; don't repeat prior work
- Document what IS — no recommendations or critique
- Always wait for all sub-agents before appending (step 4)
- Never write the follow-up section with placeholder values
