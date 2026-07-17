#!/usr/bin/env python3
"""Claude agent pipeline orchestrator.

Chains the refine>research>design>plan>implement pipeline, detecting each
stage's output file and feeding it into the next stage automatically. The
final implement stage runs to natural completion (no tagged .md output).

Multiple instances can run concurrently — each is identified by a unique
RUN_ID (e.g. "tag-a3b7c2") that gets embedded into every output filename.

Usage:
  python hack/pipeline.py "How would I add a lazy sundae mechanic?"
  python hack/pipeline.py --from-file thoughts/shared/questions/2026-04-30-ENG-tag-a3b7c2-lazy-sundae.md
  python hack/pipeline.py --resume tag-a3b7c2
  python hack/pipeline.py --list-runs
"""

import argparse
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "thoughts"))
from archive_thoughts import archive_thoughts  # noqa: E402

RUN_ID_PATTERN = re.compile(r"tag-[a-f0-9]{6}")

# Auto-advance behavior: the primary "stage finished" signal is a DONE marker
# file (.pipeline_done_<RUN_ID>) that the agent is instructed to create as its
# very last action. If the tagged output file appears but the agent never
# writes the marker (e.g. it ignored the instruction), fall back to advancing
# after this many seconds.
DONE_FALLBACK_SECONDS = 60.0
AUTO_ADVANCE_POLL_SECONDS = 2.0


def make_run_id() -> str:
    return f"tag-{secrets.token_hex(3)}"


def filename_tag_instruction(run_id: str) -> str:
    return (
        f" CRITICAL: ensure the output filename includes the tag '{run_id}' "
        f"(pass it as the ticket/description prefix to create_thought.py so the "
        f"saved file looks like YYYY-MM-DD-ENG-{run_id}-<topic>.md)."
    )


def done_file_for(run_id: str) -> Path:
    return PROJECT_ROOT / f".pipeline_done_{run_id}"


def done_marker_instruction(run_id: str) -> str:
    return (
        f" FINAL ACTION: after the output file is completely written and you have "
        f"nothing left to do, create an empty file named '.pipeline_done_{run_id}' "
        f"at the repo root (use the Write tool). This must be the very last thing "
        f"you do — the pipeline orchestrator watches for it to know this stage is "
        f"finished. Do not create it before the output file is final."
    )


def kill_process_tree(process: subprocess.Popen) -> None:
    """Terminate the claude process and every child it spawned."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # taskkill /T walks the whole tree; plain terminate() only kills the
        # root process and can orphan node children.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def to_at_reference(input_value: str) -> str:
    """Convert a file path into an @-prefixed path relative to the project root.

    Claude Code's '@' file reference inlines the file's contents directly into
    the prompt, so the agent receives the document verbatim instead of being
    told to read it from disk. Paths are emitted with forward slashes (POSIX)
    because that is what the '@' resolver expects, including on Windows.
    """
    p = Path(input_value)
    try:
        rel = p.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        rel = p
    return "@" + rel.as_posix()


PIPELINE = [
    {
        "name": "refine-research-question",
        "command": "refine-research-question",
        "output_dir": "thoughts/shared/questions",
        "context_template": "{input}",
    },
    {
        "name": "research-codebase",
        "command": "research-codebase",
        "output_dir": "thoughts/shared/research",
        "file_input": True,
        "context_template": (
            "Stage 2 of 5 (research). question file: {input}. "
            "Use the question file and conduct thorough codebase research. "
            "Save output to thoughts/shared/research/."
        ),
    },
    {
        "name": "create_design",
        "command": "create_design",
        "output_dir": "thoughts/shared/claude-code-design",
        "file_input": True,
        "context_template": (
            "Stage 3 of 5 (design). research doc: {input}. "
            "Use the research document and work with the user to settle on a design. "
            "Save output to thoughts/shared/claude-code-design/."
        ),
    },
    {
        "name": "create_plan",
        "command": "create_plan",
        "output_dir": "thoughts/shared/plans",
        "file_input": True,
        "context_template": (
            "Stage 4 of 5 (plan). design doc: {input}. "
            "Use the design document, decide phases yourself, and write a detailed "
            "actionable implementation plan. Save output to thoughts/shared/plans/."
        ),
    },
    {
        "name": "implement_plan",
        "command": "implement_plan",
        "output_dir": None,
        "terminal": True,
        "file_input": True,
        "context_template": (
            "Stage 5 of 5 (implement). plan doc: {input}. "
            "Use the implementation plan and execute every phase end-to-end with "
            "verification, per the implement_plan skill."
        ),
    },
]


def state_file_for(run_id: str) -> Path:
    return PROJECT_ROOT / f".pipeline_state_{run_id}.json"


def detect_output_with_tag(output_dir: str, run_id: str, started_at: float) -> Path | None:
    """Find newest .md file in output_dir whose name contains run_id and was
    created after started_at."""
    path = PROJECT_ROOT / output_dir
    if not path.exists():
        return None
    candidates = [
        f for f in path.glob("*.md")
        if run_id in f.name and f.stat().st_mtime >= started_at
    ]
    if candidates:
        return max(candidates, key=lambda f: f.stat().st_mtime)
    # Fallback: any file containing run_id (timestamp-relaxed)
    tagged = [f for f in path.glob("*.md") if run_id in f.name]
    if tagged:
        fallback = max(tagged, key=lambda f: f.stat().st_mtime)
        print(f"\nWARNING: No file found with mtime >= stage start; falling back to "
              f"newest tagged file: {fallback.name}")
        return fallback
    return None


def other_run_in_same_stage(run_id: str, stage_index: int) -> bool:
    """True if any other active run's state file shows it in this stage."""
    for sf in PROJECT_ROOT.glob(".pipeline_state_tag-*.json"):
        if run_id in sf.name:
            continue
        try:
            data = json.loads(sf.read_text())
        except (json.JSONDecodeError, OSError):
            return True  # unreadable state: assume a conflict rather than guess
        if data.get("current_stage") == stage_index:
            return True
    return False


def adopt_untagged_output(f: Path, run_id: str) -> Path:
    """Rename an untagged output file so it carries the run tag."""
    new = f.with_name(f"{f.stem}-{run_id}{f.suffix}")
    if not new.exists():
        f.rename(new)
        f = new
    print(f"\n[pipeline] Adopted untagged output as: {f.name}")
    return f


def recover_untagged_output(stage: dict, run_id: str, started_at: float) -> Path | None:
    """Fallback when no tagged output exists: look for an untagged .md written
    during this stage. Files tagged for another run are provably not ours, so
    only tag-free files are candidates. Adopt one only when it is provably
    ours (its content references our run_id) or when ambiguity is impossible
    (a single candidate and no concurrent run in the same stage); otherwise
    list the candidates for manual recovery."""
    path = PROJECT_ROOT / stage["output_dir"]
    if not path.exists():
        return None
    untagged = [
        f for f in path.glob("*.md")
        if f.stat().st_mtime >= started_at and not RUN_ID_PATTERN.search(f.name)
    ]
    if not untagged:
        return None
    ours = [
        f for f in untagged
        if run_id in f.read_text(encoding="utf-8", errors="ignore")
    ]
    if ours:
        return adopt_untagged_output(max(ours, key=lambda f: f.stat().st_mtime), run_id)
    if len(untagged) == 1 and not other_run_in_same_stage(run_id, PIPELINE.index(stage)):
        return adopt_untagged_output(untagged[0], run_id)
    print(f"\n[pipeline] Found untagged candidate(s) in {stage['output_dir']} but "
          f"cannot safely tell which belongs to run '{run_id}':")
    for f in sorted(untagged, key=lambda f: f.stat().st_mtime, reverse=True):
        print(f"    {f.name}")
    print(f"  If one is yours, rename it to include '{run_id}' and run: "
          f"python hack/pipeline.py --resume {run_id}")
    return None


def run_stage(stage: dict, input_value: str, run_id: str) -> Path | None:
    is_terminal = stage.get("terminal", False)
    formatted_input = (
        to_at_reference(input_value) if stage.get("file_input") else input_value
    )
    context = stage["context_template"].format(input=formatted_input)
    if not is_terminal:
        context += filename_tag_instruction(run_id) + done_marker_instruction(run_id)
    claude_arg = f"/{stage['command']} {context}"

    print(f"\n{'=' * 70}")
    print(f"  STAGE: {stage['name']}  [RUN_ID: {run_id}]")
    print(f"  INPUT: {input_value}")
    print(f"{'=' * 70}")

    done_file = done_file_for(run_id)
    if done_file.exists():
        done_file.unlink()

    popen_kwargs = {}
    if sys.platform != "win32":
        # Put claude in its own process group so kill_process_tree can killpg.
        popen_kwargs["start_new_session"] = True

    started_at = time.time()
    process = subprocess.Popen(
        [
            "claude",
            "--dangerously-skip-permissions",
            claude_arg,
        ],
        cwd=str(PROJECT_ROOT),
        **popen_kwargs,
    )

    if is_terminal:
        # Terminal stages (e.g. implement_plan) modify code rather than
        # writing a tagged .md, so there is nothing to auto-detect. Let claude
        # run to natural completion.
        process.wait()
        if process.returncode != 0:
            print(f"\nERROR: Stage '{stage['name']}' exited with code {process.returncode}.")
            return None
        # Signal success to the pipeline loop without producing a new file.
        return Path(input_value)

    auto_advanced = {"value": False}

    def watcher() -> None:
        output_seen_at: float | None = None
        while process.poll() is None:
            if done_file.exists():
                auto_advanced["value"] = True
                print(
                    f"\n[pipeline] DONE marker detected ({done_file.name}). "
                    f"Closing this agent and starting next stage.\n"
                )
                kill_process_tree(process)
                return
            if output_seen_at is None:
                output_file = detect_output_with_tag(
                    stage["output_dir"], run_id, started_at
                )
                if output_file is not None:
                    output_seen_at = time.time()
                    print(
                        f"\n[pipeline] Detected output: {output_file.name}. "
                        f"Waiting up to {DONE_FALLBACK_SECONDS:.0f}s for the "
                        f"DONE marker ({done_file.name})..."
                    )
            elif time.time() - output_seen_at > DONE_FALLBACK_SECONDS:
                auto_advanced["value"] = True
                print(
                    "\n[pipeline] No DONE marker within the fallback window; "
                    "advancing on the tagged output file alone.\n"
                )
                kill_process_tree(process)
                return
            time.sleep(AUTO_ADVANCE_POLL_SECONDS)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()

    process.wait()
    thread.join(timeout=10)

    if done_file.exists():
        done_file.unlink()

    output_file = detect_output_with_tag(stage["output_dir"], run_id, started_at)
    if output_file is None:
        output_file = recover_untagged_output(stage, run_id, started_at)

    if output_file is not None:
        print(f"\n  OUTPUT: {output_file.relative_to(PROJECT_ROOT)}")
        return output_file

    if not auto_advanced["value"] and process.returncode != 0:
        print(f"\nERROR: Stage '{stage['name']}' exited with code {process.returncode}.")
    else:
        print(f"\nERROR: No file containing tag '{run_id}' found in {stage['output_dir']}.")
        print("       Claude may have ignored the filename instruction.")
    return None


def infer_start_index(file_path: str) -> tuple[int, str]:
    """Given a --from-file path, return (next_stage_index, normalized_path)."""
    resolved = Path(file_path).resolve()
    for i, stage in enumerate(PIPELINE):
        if not stage.get("output_dir"):
            continue
        stage_dir = (PROJECT_ROOT / stage["output_dir"]).resolve()
        try:
            resolved.relative_to(stage_dir)
            return i + 1, str(resolved)
        except ValueError:
            continue
    return 0, file_path


def extract_run_id(text: str) -> str | None:
    match = RUN_ID_PATTERN.search(text)
    return match.group(0) if match else None


def list_runs() -> None:
    states = sorted(PROJECT_ROOT.glob(".pipeline_state_tag-*.json"))
    if not states:
        print("No active pipeline runs.")
        return
    print("Active pipeline runs:")
    for sf in states:
        with open(sf) as f:
            data = json.load(f)
        run_id = sf.stem.replace(".pipeline_state_", "")
        stage_name = PIPELINE[data["current_stage"]]["name"]
        print(f"  {run_id}  stage {data['current_stage'] + 1}/{len(PIPELINE)} ({stage_name})")
        print(f"    input: {data['current_input']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claude agent pipeline: refine > research > design > plan"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Initial research question (for full pipeline from scratch)",
    )
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        help="Start mid-pipeline from an existing .md file (stage inferred from path)",
    )
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Resume an interrupted run by its RUN_ID (e.g. tag-a3b7c2)",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List all interrupted runs that can be resumed",
    )
    args = parser.parse_args()

    if args.list_runs:
        list_runs()
        return

    # Determine starting stage, initial input, and RUN_ID
    if args.resume:
        run_id = args.resume
        sf = state_file_for(run_id)
        if not sf.exists():
            print(f"ERROR: No saved state for run '{run_id}'. Try --list-runs.")
            sys.exit(1)
        with open(sf) as f:
            state = json.load(f)
        start_idx = state["current_stage"]
        current_input = state["current_input"]
        print(f"Resuming run {run_id} at stage {start_idx + 1}: {PIPELINE[start_idx]['name']}")
        print(f"  Input: {current_input}")
    elif args.from_file:
        start_idx, current_input = infer_start_index(args.from_file)
        if start_idx >= len(PIPELINE):
            print("ERROR: --from-file path is from the final stage; nothing left to run.")
            sys.exit(1)
        existing = extract_run_id(current_input)
        run_id = existing or make_run_id()
        if existing:
            print(f"Detected RUN_ID '{run_id}' from filename.")
        else:
            print(f"No RUN_ID in filename; assigning new RUN_ID '{run_id}'.")
        print(f"Starting from stage {start_idx + 1}: {PIPELINE[start_idx]['name']}")
    elif args.prompt:
        start_idx = 0
        current_input = args.prompt
        run_id = make_run_id()
        print(f"Starting new pipeline with RUN_ID '{run_id}'.")
    else:
        parser.print_help()
        sys.exit(1)

    sf = state_file_for(run_id)

    for i in range(start_idx, len(PIPELINE)):
        stage = PIPELINE[i]
        if i == len(PIPELINE) - 1:
            # State is only useful for resuming earlier stages. Drop it once
            # we enter the final stage so a stale file doesn't linger.
            if sf.exists():
                sf.unlink()
        else:
            with open(sf, "w") as f:
                json.dump({"current_stage": i, "current_input": current_input}, f, indent=2)

        output_file = run_stage(stage, current_input, run_id)
        if output_file is None:
            print(f"\nPipeline stopped at stage {i + 1}: {stage['name']}.")
            print(f"Fix the issue and run: python hack/pipeline.py --resume {run_id}")
            sys.exit(1)

        current_input = str(output_file)
    print(f"\n{'=' * 70}")
    print(f"  PIPELINE COMPLETE  [RUN_ID: {run_id}]")
    print(f"  Plan implemented from: {current_input}")
    print(f"{'=' * 70}\n")

    print(f"[pipeline] Auto-archiving thoughts/shared/ for run {run_id}...")
    try:
        moved = archive_thoughts(run_id=run_id)
        if moved:
            print(f"[pipeline] Sent {len(moved)} file(s) to the Recycle Bin:")
            print("\n".join(moved))
        else:
            print("[pipeline] Nothing to archive.")
    except Exception as exc:
        print(f"[pipeline] WARNING: archive step failed: {exc}")


if __name__ == "__main__":
    main()
