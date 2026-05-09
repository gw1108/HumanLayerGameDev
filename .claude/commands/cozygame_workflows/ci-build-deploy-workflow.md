# CI Build & Deploy Workflow Modifier

**When to use:** Editing `.github/workflows/main.yml` — the GitHub Actions pipeline that version-bumps, builds WebGL via Unity, uncomments the `autoSyncPersistentDataPath` line, zips the output, uploads to itch.io via butler, and commits the version bump back to `main`.

**Scope:** Everything an agent needs to modify the CI pipeline without re-reading the whole repo. Covers the triggers (manual + scheduled), the gate job, the build-and-deploy job, and the Unity-side build script the workflow calls into.

---

## Pipeline at a Glance

Two triggers, one build job, gated:

1. **`workflow_dispatch`** (manual) → always proceeds.
2. **`schedule`** (`cron: '30 11 * * *'` = 03:30 PST / 04:30 PDT) → gated: proceeds only if **commits in past 24h touched Unity build inputs** (`Assets/`, `Packages/`, `ProjectSettings/`, or `steam_appid.txt`) AND **no prior run of this workflow in past 12h**. Commits limited to `.claude/`, `thoughts/`, docs, etc. do not trigger a nightly build.

Flow: **`gate` job → `build-and-deploy` job** (via `needs: gate` + `if: needs.gate.outputs.proceed == 'true'`).

Inside `build-and-deploy`:
Free disk → Move Docker root to `/mnt` → Sparse checkout → LFS cache + pull → Library cache → **Bump patch version** (sed on `ProjectSettings.asset`) → **Unity WebGL build** (GameCI, calls `BuildScript.BuildWebGL`) → Locate zip in `Builds/` → Upload artifact → Setup butler → **`butler push` to itch.io** → **Git commit + pull-then-push with retries** to write the version bump back to `main`.

---

## Files and Their Roles

| File | Role | When You Touch It |
|------|------|-------------------|
| `.github/workflows/main.yml` | The entire pipeline (triggers, gate, build, deploy, commit-back) | Almost every CI change |
| `Assets/Editor/BuildScript.cs` | Unity-side build entry points. `BuildWebGL()` calls `Run()` → `PatchWebGLIndex()` → `ZipWebGLBuild()`. Reads `-outputDir` CLI arg. | When changing build output layout, what gets patched in `index.html`, or zip naming |
| `ProjectSettings/ProjectSettings.asset` | Line ~146: `bundleVersion: x.y` or `x.y.z`. Parsed/incremented by the `Bump patch version` step. | Never directly — the workflow mutates it |
| `build.bat` | Local-dev analog of the CI build. Uses same `BuildScript.BuildWebGL` method, same `-outputDir` arg contract. | When you change the CLI contract of `BuildScript` — keep both in sync |
| `README.md` | Human docs; mentions the "uncomment `config.autoSyncPersistentDataPath = true;`" requirement | Rarely; only if you change the manual-release instructions |

---

## Core Concepts

### The gate job is lightweight and checkout-less

`gate` runs on `ubuntu-latest` with `permissions: { contents: read, actions: read }` and **no checkout step**. It uses `gh api` and `gh run list` (with `--repo "${{ github.repository }}"` — required because there's no `.git/config` to infer from). Runs for a few seconds on skip days.

Gate logic:
- `workflow_dispatch` → always proceed (explicit bypass at top of script).
- `schedule` → Gate 1: `gh api /repos/.../commits?sha=<default_branch>&since=<24h ago>` to list SHAs **excluding commits by `github-actions[bot]`** (e.g. version-bump commits), then `gh api .../commits/{sha} --jq '.files[].filename'` for each, then `grep -E '^(Assets/|Packages/|ProjectSettings/|steam_appid\.txt$)'`. Gate 2: `gh run list --repo ... --workflow main.yml --created ">12h ago"` filtered to exclude `${{ github.run_id }}`.
- On skip, exits `0` with `proceed=false` (not a failure — no red-X emails).

### The build job is disk-constrained

Unity WebGL Docker image is ~20GB; `ubuntu-latest` has only ~14GB free on `/`. Two mandatory steps preserve this:
1. `jlumbroso/free-disk-space@main` — reclaims ~30GB (android, dotnet, haskell, large-packages, docker-images, swap).
2. Move Docker data-root from `/var/lib/docker` to `/mnt/docker/lib`, restart Docker. `/mnt` has ~75GB.

**Do not remove either step.** The "no space left on device" failure pre-dates the current workflow.

### Sparse checkout + LFS cache

```yaml
sparse-checkout: |
  Assets
  Packages
  ProjectSettings
```
Cone mode — includes listed dirs + all root files. Excludes `.claude`, `.bezisidekick`, `.idea`, `idbfs`, `thoughts`, etc., which Unity doesn't need for a build.

LFS is cached by content hash: `git lfs ls-files --long | cut -d ' ' -f1 | sort > .lfs-assets-id`, then `actions/cache@v4` keyed on `hashFiles('.lfs-assets-id')`. Then `git lfs pull` + a log line reporting the materialized file count. LFS runs on **both** manual and scheduled invocations (same job).

### Version bump is plain `sed`

Reads `bundleVersion: <value>` via `awk`, parses as 2-part (`x.y`) or 3-part (`x.y.z`), increments last component, writes back via `sed`. Emits `steps.version.outputs.version` for downstream steps (`butler push --userversion`, commit message).

### Unity build is called via GameCI

```yaml
uses: game-ci/unity-builder@v4
with:
  unityVersion: ${{ env.UNITY_VERSION }}   # 6000.3.8f1
  targetPlatform: WebGL
  buildMethod: BuildScript.BuildWebGL
  customParameters: -outputDir ${{ env.OUTPUT_DIR }}   # Builds/Build_WebGL
  allowDirtyBuild: true                                 # tolerates version-bump dirty state
```

GameCI supplies `editor-ubuntu-6000.3.8f1-webgl-3.2.2` automatically — no manual image selection needed.

`BuildScript.BuildWebGL`:
1. `Run(BuildTarget.WebGL, null)` → writes to `outputDir`.
2. `PatchWebGLIndex(outputDir)` → regex-replaces `//\s*(config.autoSyncPersistentDataPath\s*=\s*true\s*;)` with `$1`. Warns (does not fail) if the pattern isn't found.
3. `ZipWebGLBuild(outputDir)` → writes `{ProductName}_{Version-with-dots-as-underscores}.zip` to **`outputDir`'s parent** (i.e., `Builds/`, not inside `Builds/Build_WebGL/`).

### Artifact discovery and upload

The `Locate WebGL zip` step does `ls Builds/*.zip | head -n1` because the exact zip name depends on Unity's `productName` + `bundleVersion`. If `BuildScript.ZipWebGLBuild` ever changes the output path, update this step.

`butler push` invocation:
```
butler push <zip> cnava/good-laundry-great-laundry:webgl --userversion <version>
```
- `cnava` (lowercase, Christian Nava's itch account) owns the `BUTLER_API_KEY`. Not `GeorgeWang` / `georgewang`.
- Channel `webgl` is created on first push.

### Commit-back is race-safe

After butler succeeds, the workflow pushes the `ProjectSettings.asset` version bump to `main`. The loop:
```
for attempt in 1 2 3:
  git fetch origin main
  git merge --no-edit --strategy-option=theirs origin/main
  git push origin HEAD:main
```
- `-X theirs` means **main wins conflicts** — this can silently discard the version bump if someone else bumped the version between our fetch and push. Acceptable trade-off for "never block the workflow."
- Commit message includes `[skip ci]` so the push doesn't retrigger the workflow.
- `permissions: contents: write` on `build-and-deploy` is required for this push; `GITHUB_TOKEN` handles auth automatically.

---

## Secrets and Permissions

Required secrets (Repo Settings → Secrets and variables → Actions):
- `UNITY_LICENSE` / `UNITY_EMAIL` / `UNITY_PASSWORD` — for GameCI activation.
- `BUTLER_API_KEY` — generated at https://itch.io/user/settings/api-keys by the account that owns `good-laundry-great-laundry` (currently `cnava`). If ownership moves, rotate this key.
- `GITHUB_TOKEN` — provided automatically; no setup needed.

Job-level `permissions`:
- `gate`: `contents: read`, `actions: read` (latter required for `gh run list`).
- `build-and-deploy`: `contents: write` (for the version-bump push).

---

## Common Modifications (with Ready-Made Starting Points)

### "Change which paths trigger the nightly build"

Gate 1 already path-filters against `^(Assets/|Packages/|ProjectSettings/|steam_appid\.txt$)`. To add or remove watched paths, edit that single `grep -qE` regex in `.github/workflows/main.yml`. Anchor directories with a trailing slash (`Foo/`) and exact filenames with `$` (`bar\.txt$`). Gate 2 (12h anti-duplicate) sits below Gate 1 and is independent.

**Alternative** for *manual* path-filtering on `push:` triggers (not applicable here since we use `workflow_dispatch` + `schedule`): `on.push.paths:` filter. Don't confuse the two — `paths:` is a GitHub-native filter that doesn't work on `schedule:` or `workflow_dispatch:`.

### "Change the nightly time"

Cron is UTC-only, no TZ field. Current: `30 11 * * *` = 03:30 PST (Nov–Mar) / 04:30 PDT (Mar–Nov). For 03:30 **PDT** year-round-ish, use `30 10 * * *` (which drifts to 02:30 PST in winter). There is no clean "always 3:30 local." If you really need that, schedule two cron lines and accept one will skip during the changeover hour.

### "Build an additional platform (Linux/Windows/Android)"

`BuildScript.cs` already has `BuildWindows()`, `BuildLinux()`, `BuildAndroid()` methods. Pattern per platform:
1. Add a new job (or parallel matrix entry) with a different `targetPlatform` + `buildMethod`.
2. Pick a different `OUTPUT_DIR` per platform so artifacts don't collide.
3. Android requires keystore secrets — see `build.bat:142-149` for the env var contract (`ANDROID_KEYSTORE_PATH/PASS`, `ANDROID_KEYALIAS_NAME/PASS`) that `BuildScript.ConfigureAndroidSigning` expects.
4. butler supports multiple channels under one game — use `:win-x64`, `:linux-x64`, `:android` channel names alongside the existing `:webgl`.

### "Switch itch target or username"

Edit the three `env:` vars at the top: `ITCH_USERNAME`, `ITCH_GAME_SLUG`, `ITCH_CHANNEL`. Then rotate `BUTLER_API_KEY` if ownership changes accounts (itch API keys are per-user). Validate with `butler status "${ITCH_USERNAME}/${ITCH_GAME_SLUG}"` from a local shell before pushing the change — a response of `no channel found for ...` means success (auth OK, channels not yet created); `invalid game` means wrong slug/username.

### "Add a pre-build test step"

Insert between `Cache Library` and `Bump patch version`. Use `game-ci/unity-test-runner@v4` with the same `UNITY_LICENSE` secrets. Note this roughly doubles Unity minutes consumed. Fail-fast on test failures is the default.

### "Change what gets patched in index.html"

Edit the regex in `BuildScript.cs:92` (`PatchWebGLIndex`). Current pattern: `@"//\s*(config\.autoSyncPersistentDataPath\s*=\s*true\s*;)"`. The method warns-but-doesn't-fail when the pattern isn't matched — change to `EditorApplication.Exit(1)` if you want to enforce the patch.

### "Change zip naming or location"

Edit `BuildScript.ZipWebGLBuild` (`BuildScript.cs:106-119`). Currently produces `{ProductName}_{Version-underscored}.zip` in the parent of `-outputDir`. The workflow's `Locate WebGL zip` step uses `ls Builds/*.zip | head -n1` — if you move the zip elsewhere, update that glob.

### "Skip the version commit-back"

Remove the entire `Commit version bump` step. You'll also want to remove the `permissions: contents: write` on the job (downgrade to `contents: read`). Note that this decouples `bundleVersion` in source from what's shipped — itch will still receive the incremented `--userversion` from butler, but the repo won't track it.

### "Disable the cron but keep manual"

Delete lines 5–7 of `main.yml` (the `schedule:` block and its cron). The gate job can stay — the `workflow_dispatch` branch is self-contained. Or, simpler: delete the whole `gate` job and make `build-and-deploy` top-level; remove `needs: gate` + `if: needs.gate.outputs.proceed`.

---

## Gotchas

- **GitHub cron is UTC-only.** All nightly time changes are UTC math. No timezone support; ±1h DST drift for PST schedules.
- **`gh run list` needs `--repo` when run without a checkout.** It tries to read `.git/config` otherwise — this bit the nightly build once already (fix is live in the gate step).
- **`-X theirs` silently discards the CI version bump on conflict.** Deliberate trade-off. If concurrent version bumps matter, switch to `-X ours` + handle the push failure explicitly.
- **GameCI's `allowDirtyBuild: true` is required** because the Bump step modifies `ProjectSettings.asset` before the build starts.
- **Scheduled workflows auto-disable after 60 days of repo inactivity.** Harmless here (no commits = gate would've skipped anyway), but worth knowing.
- **Itch.io usernames are case-sensitive in butler targets.** Use lowercase (`cnava`, not `Cnava`).
- **`[skip ci]` in commit messages only prevents *this* workflow from retriggering on push** — it doesn't affect workflows listening to other events.
- **`fetch-depth: 1` + sparse checkout is intentional** for speed. The commit-back step explicitly `git fetch origin main` before merging/pushing — it doesn't rely on local history.
- **The `build.bat` local script and the CI both call `BuildScript.BuildWebGL` with `-outputDir`.** Keep the CLI arg contract (`-outputDir <path>`) stable, or update both at once.

---

## Verification Checklist Before Merging CI Changes

- [ ] Manually dispatch the workflow from GitHub UI → full build/deploy path succeeds end-to-end.
- [ ] Check the **Locate WebGL zip** step log — confirms a zip was produced at the expected location.
- [ ] Check the **Pull LFS objects** step log — reports a non-zero materialized file count once LFS assets exist in the repo.
- [ ] Check the **Commit version bump** step log — either reports "No version change to commit" (if idempotent) or shows a successful push.
- [ ] Visit `https://cnava.itch.io/good-laundry-great-laundry` (or `butler status cnava/good-laundry-great-laundry:webgl`) → confirm the new channel upload landed with the expected `--userversion`.
- [ ] For gate-logic changes: force a scheduled-style evaluation by temporarily adding `push:` to the triggers and pushing a no-op commit. Remove `push:` before merging.
