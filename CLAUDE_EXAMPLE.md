# Claude.md

The role of this file is to describe common mistakes and confusion points that agents might encounter as they work in this project. If you ever encounter something in the project that surprises you, please alert the developer working with you and indicate that this is the case in the AgentMD file to help prevent future agents from having the same issue.

---

## Operating Principles (Non-Negotiable)

- **Smallest change that works**: Implement the simplest solution for simple problems, better solutions for harder problems. Do not over-engineer or add flexibility that isn't needed yet.
- Don't touch unrelated code but please do surface bad code or design smells you discover with me so we can address them as a separate issue.
- I'm always open to ideas on better ways to do things. Please don't hesitate to suggest a better way, or one that has long lasting impact over a tactical change. (as a few examples)
- **Leverage existing patterns**: Follow established project conventions before introducing new abstractions or dependencies.
- **Be explicit about uncertainty**: Ask, don't assume. If something is unclear, ask before writing a single line. Never make silent assumptions about intent, architecture, or requirements. When running unattended, pick the most reasonable interpretation, proceed, and record the assumption rather than blocking.
- If something is described or asked for do not ask for confirmation.
- No performative tics: no unnecessary validation ("Fair point"), narrating the next move ("Let me name them plainly"), flagging significance ("This is the real issue"), or advertising honesty ("to be honest"). Lead with substance.
- In files and in chat, including inside code blocks, Claude writes text as continuous lines with no hard wrapping at fixed column widths and no leading-space alignment. Structural formatting (headers, separators, indented lists) is fine.

---

## Project Structure

All game assets live under `/Assets`. The project is using Unity 6000.4.7f1 Personal

- **Gameplay code** → `/Assets/_Scripts`
- **Editor-only scripts** → `/Assets/Editor` (e.g., `BuildScript.cs`). It's ok to create setup scripts in the Editor folder, but if they are only meant to be run once the agent should just run the script where it needs to be run then delete the script afterwards. Do not ask for permission or leave running an editor script to the user. Just run the editor scripts yourself when needed.
- **Materials** → `/Assets/Materials`
- **Prefabs** → `/Assets/_Prefabs`
- **Scenes** → `/Assets/Scenes`
- **ScriptableObjects** → `/Assets/ScriptableObjects`
- **2D Textures / sprites / UI Textures** → `/Assets/Textures`, and `/Assets/Textures/kenney_fantasy-ui-borders` for UI.
- **Shaders** → `/Assets/Shaders`
- **Animations** → `/Assets/Animations`
- **Audio (music & SFX)** → `/Assets/Audio` — **use `.wav` (PCM) or `.ogg` (Vorbis); never `.mp3`.** When replacing an `.mp3`, reuse the old `.meta` `guid` so prefab/`SfxClips`/`MusicClips` references survive — and if the Editor is open it may auto-generate a fresh `.meta` with a new guid, so restore the original guid afterward.
- **Third-party** → `/Assets/Plugins` or `/Assets/TextMeshPro` (do not modify or scan unless explicitly needed)
- **3D Models** → `/Assets/Synty` for something usable

Do NOT modify or scan files in the /thoughts/ folder unless specified. Do NOT scan files in any /ARCHIVE/ folder unless specified.

---

## Art assets

When a task needs a 3D model or art asset, in priority order:
1. Search the premade asset packs under `/Assets/Synty` for something usable or `/Assets/Textures/kenney_fantasy-ui-borders` for UI.
2. If nothing fits, use the 3D modeling skills (`create-3d-asset` / `generate-3d-asset-hunyuan`).
3. If that fails, fall back to Unity primitives.

### UI text glyphs

Every TMP label in the project uses `LiberationSans SDF`, whose atlas is **static** — 250 glyphs, roughly ASCII plus Latin-1. Anything outside it (e.g. `✕` U+2715) renders as a missing-glyph box. `·` U+00B7 and `×` U+00D7 are in the atlas and are what the existing UI uses; reach for those before assuming a nicer symbol will draw.

---

### Code Intelligence

Prefer LSP over Grep/Glob/Read for code navigation:
- `goToDefinition` / `goToImplementation` to jump to source
- `findReferences` to see all usages across the codebase
- `workspaceSymbol` to find where something is defined
- `documentSymbol` to list all symbols in a file
- `hover` for type info without reading the file
- `incomingCalls` / `outgoingCalls` for call hierarchy

Before renaming or changing a function signature, use
`findReferences` to find all call sites first.

Use Grep/Glob only for text/pattern searches (comments,
strings, config values) where LSP doesn't help.

After writing or editing code, check LSP diagnostics before
moving on. Fix any type errors or missing imports immediately.

---

## Workflow Orchestration

### 1. Subagent Strategy (Parallelize Intelligently)
- Use subagents to keep the main context clean and to parallelize:
  - repo exploration, pattern discovery, test failure triage, dependency research, risk review.
- Give each subagent **one focused objective** and a concrete deliverable:
  - "Find where X is implemented and list files + key functions" beats "look around."
- Merge subagent outputs into a short, actionable synthesis before coding.

### 2. Incremental Delivery (Reduce Risk)
- Prefer **thin vertical slices** over big-bang changes.

### 3. Self-Improvement Loop
- After any user correction or a discovered mistake, add a new entry to `tasks/lessons.md`.
- Keep each entry minimal: a short **category header** (e.g. `### Research scoping`) plus a **one-line prevention rule**. Nothing else.
- The category lets future agents skim and skip entries that look unrelated without reading the body. If a rule needs more context to be actionable, the category itself is too broad.