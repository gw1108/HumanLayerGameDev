# pipeline.py

`pipeline.py` orchestrates the full **refine → research → design → plan → implement** chain end-to-end so you don't have to copy file paths between stages by hand. It launches `claude` with the appropriate slash command for each stage, watches the stage's output directory, auto-detects the new `.md` file when it lands, gives Claude a few seconds to finish its closing message, then terminates that agent and feeds the file path into the next stage.

## The five stages

| # | Stage | Slash command | Output |
|---|-------|---------------|--------|
| 1 | Refine the question | `/refine-research-question` | `thoughts/shared/questions/*.md` |
| 2 | Research the codebase | `/research-codebase` | `thoughts/shared/research/*.md` |
| 3 | Settle on a design | `/create_design` | `thoughts/shared/claude-code-design/*.md` |
| 4 | Write an implementation plan | `/create_plan_greenunity` | `thoughts/shared/plans/*.md` |
| 5 | Execute the plan | `/implement_plan_yolo` | Code changes (runs to natural completion) |

## How auto-advance works

Each run gets a unique `RUN_ID` like `tag-a3b7c2`. The pipeline injects an instruction into every prompt telling Claude to embed that tag in the saved filename (via `create_thought.py`). A background watcher polls the stage's output directory; as soon as a `.md` file containing the tag appears with an mtime after the stage started, the pipeline waits `AUTO_ADVANCE_GRACE_SECONDS` (5s) for Claude's wrap-up text, then `terminate()`s the agent and starts the next stage with the new file path as input.

Because the tag is unique per run, multiple pipelines can run concurrently without stepping on each other.

## Usage

```bash
# Full pipeline from a fresh question
python hack/pipeline.py "How would I add a lazy sundae mechanic?"

# Start mid-pipeline from an existing artifact (stage inferred from the path)
python hack/pipeline.py --from-file thoughts/shared/research/2026-04-30-ENG-tag-a3b7c2-lazy-sundae.md

# Resume an interrupted run
python hack/pipeline.py --resume tag-a3b7c2

# See what runs can be resumed
python hack/pipeline.py --list-runs
```

## State and recovery

Between stages, the pipeline writes `.pipeline_state_<RUN_ID>.json` at the project root containing the current stage index and input path. If a stage fails (Claude exits non-zero, or no tagged file appears in the expected directory), the pipeline prints the resume command and exits. The state file is deleted on successful completion of stage 5.

The final implement stage has no tagged `.md` output — it modifies code instead — so it runs to natural completion rather than being auto-terminated.
