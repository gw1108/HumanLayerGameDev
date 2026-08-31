---
name: giga-audit-and-fix
description: >
  Audit implementation plans, PRs, architectures, or existing codebases using multi-perspective
  expert critique plus workspace verification, then dispatch fresh agents to implement every
  approved fix and independently verify it. Use when asked to find *and* fix issues, remediate
  an existing audit, or clean up a codebase end-to-end — not when a review document alone is wanted
  (use giga-audit for that).
---

# Giga-Audit-and-Fix Pipeline

Use this skill to review a plan, architecture, or codebase for bugs, security flaws, performance
bottlenecks, and edge cases — and then actually fix what you find, with independent verification.

> Harness-agnostic: this skill runs under any agent harness (Claude Code, Antigravity, etc.). It
> describes *capabilities*, not fixed tool names — use whichever tool in your harness provides each
> capability (examples given per phase).

**Split the work across three roles.** The auditor (Phases 1-4) finds and records issues. The fixers
(Phase 6) implement them. The verifier (Phase 7) confirms the fixes. Each fixer and the verifier must
be a **fresh agent** — a subagent, or a new session handed only the ledger path. This is not
ceremony: the auditor's context is full of discarded hypotheses, and an agent that wrote a finding
will defend it instead of satisfying it.

If a `giga-audit` report already exists for this target, skip Phases 1-3 and convert it in Phase 4.

## Phase 1: Reviewer Personas
Brainstorm 3-4 expert reviewer personas critical to the target domain (e.g., Security Lead,
Performance Engineer, QA Tester, Rollback Specialist).

## Phase 2: Critical Questioning
Generate 3 risk-focused questions or concerns per persona based on the proposed plan or codebase.

## Phase 3: Workspace Verification
Investigate the codebase to confirm whether each risk is real **before** recording it:
1. **Narrow down files** with your harness's content-search tool — Claude Code `Grep`/`Glob`;
   Antigravity `grep_search`. If unavailable or it errors, fall back to a shell search via the
   run-command/`Bash` tool (PowerShell `Select-String -Path ... -Pattern ...`, or `findstr`/`grep`).
2. **Read only the relevant line ranges** with your file-read tool — Claude Code `Read` with
   `offset`/`limit`; Antigravity `view_file` with `StartLine`/`EndLine`. Do not load large files in full.
3. **Discard any risk you cannot confirm against the actual code.** Record only verified issues, each
   backed by concrete evidence.

## Phase 4: Findings Ledger
Write the verified findings to a Markdown file — this is a handoff contract for the fixers, not a
report for a human, so the schema is rigid. One block per finding, IDs assigned in severity order:

```markdown
### F-003 · HIGH · auto-fix
**Location:** `src/net/session.py:142-160`
**Issue:** Reconnect path never clears the pending-ack buffer.
**Evidence:** <the exact snippet read in Phase 3>
**Fix:** Clear `self._pending` in `_on_disconnect` before re-handshake.
**Blast radius:** `src/net/session.py`
**Verification:** `pytest tests/net/test_session.py -k reconnect`
**Status:** - [ ] not started
```

Four fields carry the pipeline; get them right:
- **Disposition** (in the heading, after severity) — one of:
  - `auto-fix` — cause is understood, the fix is local, and behavior visible outside the module is
    unchanged.
  - `needs-decision` — real issue, but the fix changes a public API or observable behavior, or there
    is more than one defensible fix. Never dispatched without the user promoting it in Phase 5.
  - `won't-fix` — verified but out of scope; recorded so it isn't rediscovered later. State why.
- **Blast radius** — every file the fix may touch. This drives scheduling in Phase 6, so be honest:
  under-declaring causes edit conflicts.
- **Verification** — a command that actually runs (test, build, lint, or a `grep` asserting an
  invariant). "Confirm the buffer is cleared" is not a verification. If you cannot write a runnable
  check for a finding, its disposition is `needs-decision`, not `auto-fix`.
- **Status** — the checkbox each fixer flips, appending one line on what it changed.

Give the user the ledger path.

## Phase 5: Triage Gate
Present the ledger grouped by disposition — counts plus one-line summaries, not the full blocks — and
get a single approval before anything is executed. The user may promote `needs-decision` items to
`auto-fix`, demote anything to `won't-fix`, or edit the ledger directly. **This is the only human
checkpoint; do not skip it, and do not pause again during Phase 6.** If the user has already said to
fix everything without stopping, state which `needs-decision` items you are promoting and continue.

## Phase 6: Dispatch
1. **Isolate the work.** Create a branch (or a worktree) before the first edit.
2. **Cluster by blast radius.** Group findings whose file sets overlap — transitively — into one
   cluster. Findings in the same cluster share code and must be fixed by the same agent, sequentially;
   clusters with disjoint file sets may run in parallel. Never dispatch one agent per finding when
   findings touch the same file: concurrent edits conflict and silently drop each other's work.
3. **Dispatch one fresh fixer per cluster**, using your harness's subagent capability (Claude Code
   `Agent`; otherwise a new session). Give each fixer only: the ledger path, its finding IDs, and
   these standing orders:
   - Read the assigned findings and the full files they touch — no line-range shortcuts here; the
     auditor read narrowly, the fixer needs whole-file context.
   - Fix exactly the assigned findings. **No adjacent cleanup, refactors, or drive-by improvements.**
   - Run each finding's Verification command; do not move on until it passes.
   - Commit per finding, message referencing the ID (`F-003: clear pending-ack buffer on reconnect`),
     so any single fix can be reverted.
   - Check off `**Status:**` in the ledger and append what was changed.
   - On mismatch — the code doesn't look like the finding describes, or the stated fix is wrong —
     **STOP that finding, leave it unchecked, and report**, then continue with the rest:
     ```
     Issue with F-00N:
     Expected: [what the ledger says]
     Found: [actual situation]
     Why this matters: [explanation]
     ```
     Do not improvise a different fix.
4. **Re-check between clusters.** A completed fix can invalidate a pending finding. Before starting a
   cluster, confirm its findings still apply to the current code; mark any that no longer do as
   resolved-by-side-effect rather than editing blindly.

## Phase 7: Independent Verification
Dispatch one final fresh agent — not any fixer — with the ledger path and the branch. It must:
1. Re-run Phase 3 verification for every finding marked done, against the **changed** code. The
   question is whether the cause is gone, not whether an edit was made — a patch at the call site
   that leaves the broken function intact fails this check.
2. Run the full test suite and build to catch regressions and interactions between fixes.
3. Report per finding: `fixed` / `not fixed` / `regressed something else`.

Anything that fails comes back as a **new finding appended to the ledger** with a fresh ID, not as a
retry in place. Re-enter at Phase 5 with those. Then summarize for the user: findings by disposition,
what was fixed and verified, what remains open and why, and the branch name.
