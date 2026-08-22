---
name: giga-audit
description: >
  Review implementation plans, PRs, architectures, or existing codebases using
  multi-perspective expert critique plus workspace verification, to find bugs,
  security flaws, performance bottlenecks, and edge cases. Use when asked to
  audit/review a plan or codebase for risks, or to pressure-test a design before building.
---

# Giga-Audit Pipeline

Use this skill to review implementation plans, architectures, or existing codebases to find bugs, security flaws, performance bottlenecks, and edge cases.

> Harness-agnostic: this skill runs under any agent harness (Claude Code, Antigravity, etc.). It describes *capabilities*, not fixed tool names — use whichever tool in your harness provides each capability (examples given per phase).

## Phase 1: Reviewer Personas
Brainstorm 3-4 expert reviewer personas critical to the target domain (e.g., Security Lead, Performance Engineer, QA Tester, Rollback Specialist).

## Phase 2: Critical Questioning
Generate 3 risk-focused questions or concerns per persona based on the proposed plan or codebase.

## Phase 3: Workspace Verification
Investigate the codebase to confirm whether each risk is real **before** reporting it:
1. **Narrow down files** with your harness's content-search tool — Claude Code `Grep`/`Glob`; Antigravity `grep_search`. If unavailable or it errors, fall back to a shell search via the run-command/`Bash` tool (PowerShell `Select-String -Path ... -Pattern ...`, or `findstr`/`grep`).
2. **Read only the relevant line ranges** with your file-read tool — Claude Code `Read` with `offset`/`limit`; Antigravity `view_file` with `StartLine`/`EndLine`. Do not load large files in full.
3. **Discard any risk you cannot confirm against the actual code.** Report only verified issues, each backed by concrete evidence.

## Phase 4: Audit Synthesis
Write the audit report to a Markdown file using your harness's file-write tool, then give the user the file path. Use this structure:
- **Identified Issues**: Grouped by severity (High, Medium, Low) or component.
- **Evidence**: Clickable file links and specific code snippets/line ranges.
- **Recommended Mitigations**: Concrete, actionable steps to resolve each issue.
