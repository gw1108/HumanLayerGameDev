# Tutorial System Modifier Workflow

**When to use:** Adding, modifying, or removing tutorials in response to new clothing conditions (lint, stains, wrinkles, tears, etc.), new tools, new placement zones, new minigames, or new characters/story beats.

**Scope:** Everything an agent needs to extend the tutorial system without reading the entire codebase. Pair with a quick read of `TutorialManager.cs` before making non-trivial changes.

---

## System at a Glance

The tutorial system is a **singleton-driven, data-light, code-triggered overlay**. Tutorials:

1. Are **authored as ScriptableObject assets** (`Assets/ScriptableObjects/Tutorials/Tutorial_*.asset`) dragged into `TutorialManager.tutorialAssets` in the scene inspector.
2. Are **gated by FBPP persistence** — once a tutorial is marked completed, it never shows again on that device until `ClearAll()` is called.
3. Are **triggered from gameplay code** at the moment the player encounters a teachable situation.
4. Are **completed by gameplay code** when the player successfully performs the taught action.

**Important:** The system does not auto-detect "first use." The gameplay code is responsible for both the trigger (`TryShowTutorial`) and the completion (`MarkTutorialCompleted`). Missing either call is the #1 cause of broken tutorials.

---

## Files and Their Roles

| File | Role | When You Touch It |
|------|------|-------------------|
| `Assets/_Scripts/UI/TutorialSO.cs` | Plain `[Serializable]` class: `Text` + `ShowPointer` | Rarely — only to add new fields like audio clips |
| `Assets/_Scripts/UI/TutorialManager.cs` | Singleton orchestrator: IDs, persistence, gating, show/hide API | Every time you add a new tutorial (enum + inspector entry) |
| `Assets/_Scripts/UI/Tutorial.cs` | Text bubble + calls into `FocusBox` | When display/lifecycle changes |
| `Assets/_Scripts/UI/FocusBox.cs` | Dim overlay + highlight box + pointer (world-space SpriteRenderer with DOTween loop) | When focus visuals need a new mode |
| `Assets/_Scripts/UI/TutorialIdExtensions.cs` | `GetTutorialKey(this TutorialId)` → `"Tutorial" + id.ToString()` | Never (stable) |
| *Gameplay code* (tools, zones, minigames, cloth conditions) | **Integration points** — where tutorials are triggered and completed | **Most common edit** |

---

## Core Concepts

### TutorialSO (a real ScriptableObject)

`TutorialSO` is a `ScriptableObject` with `[CreateAssetMenu(menuName = "CozySim/Tutorial/Tutorial")]`. Each tutorial has its own `.asset` file under `Assets/ScriptableObjects/Tutorials/`. At `Awake`, `TutorialManager` builds a runtime `Dictionary<TutorialId, TutorialSO>` from its `tutorialAssets` list for O(1) lookup.

```csharp
[CreateAssetMenu(fileName = "Tutorial", menuName = "CozySim/Tutorial/Tutorial")]
public class TutorialSO : ScriptableObject
{
    public TutorialManager.TutorialId Id;    // Lookup key — must be unique
    [TextArea(2, 5)] public string Text;
    public bool ShowPointer = true;
    public int Priority = 0;                 // Higher wins when two tutorials race
    public Vector3 PointerOffset = Vector3.zero; // Per-tutorial pointer nudge; zero = FocusBox default
}
```

Assets are dragged into `TutorialManager.tutorialAssets` in the scene inspector. The manager ignores duplicates — first asset wins for a given `Id`.

### Persistence Key

Each tutorial is gated by an FBPP bool at the key `"Tutorial" + id.ToString()` (see `TutorialIdExtensions.GetTutorialKey`). `MarkTutorialCompleted(id)` sets the bool; `ClearTutorials()` deletes every entry's bool.

### Global Disable

If `FBPP.GetBool(PlayerOptions.DisableTutorials, false)` is `true`, every `TryShow…` call returns `false` immediately and logs `"Player has tutorials disabled!"`. Respect this when debugging — tutorials won't appear in that user setting state.

---

## Focus Modes (choose one per tutorial)

| Mode | API | Use When |
|------|-----|----------|
| **UI focus** | `TryShowTutorial(id, RectTransform focus, …)` | Teaching about a UI button, panel, HUD element |
| **World focus** | `TryShowTutorial(id, Transform worldTarget, Camera, …, Vector3 customPointerOffset)` | Teaching about a 2D/3D object in the scene — a tool, a piece of cloth, a zone |
| **Animated pointer** | `TryShowTutorialAnimatedPointer(id, Transform startTarget, Transform destinationTarget, Camera, …)` | Teaching a *workflow* — "move this from here to there." Pointer loops between the two targets with rotation delta and pause. |
| **No focus** | `TryShowTutorial(id, focus: null, …)` (UI overload, null focus) | Welcome/story dialogue with no visual target. The text bubble still shows; FocusBox stays hidden. |

---

## The Standard Pattern (Memorize This)

Almost every tutorial in the codebase follows the same lifecycle. Copy it exactly:

```csharp
// 1) Trigger: fire when the teachable situation first arises.
//    TryShowTutorial is a no-op if already seen, so it's safe to call often.
TutorialManager.Instance.TryShowTutorial(
    TutorialManager.TutorialId.MyNewTutorial,
    worldTarget,                      // or RectTransform
    camera,                           // omit for UI overload
    forcePlayerToClickFocus: true,    // gate input to the focus box
    waitSeconds: -1f,                 // -1 = immediate, 0 = next frame, >0 = delay
    Vector3.zero                      // customPointerOffset (world overload only)
);

// 2) Complete: fire when the player successfully does the taught thing.
TutorialManager.Instance.MarkTutorialCompleted(TutorialManager.TutorialId.MyNewTutorial);
```

**Real examples in the codebase:**
- `ToolTutorialBeats.cs` / `LintRoller.cs` — `HandleItemPlaced` triggers pickup tutorial when lint cloth is placed; `CompleteAndReturn` marks both ids complete after successful lint removal
- `MinigameManager.cs:363` — trigger `WelcomeBeginner` on first minigame item
- `FoldableBase.cs:127` — complete `FoldingClothesBeginner` after first successful fold
- `Washer.cs:125` — complete the washer tutorial when a cycle starts

---

## World-Target Convention: Always Prefer `GetActualTransformPos()`

When the focus target is a component whose visual sprite is offset from its `transform.position` (collider buttons, anything where the renderer is a child), passing raw `target.transform` puts the FocusBox/pointer on the logical pivot, not on the thing the player actually sees. The convention in this codebase is:

> **Whenever a class exposes `GetActualTransformPos()`, the world-overload of `TryShowTutorial` MUST receive that result instead of `.transform`.**

`ColliderButton.GetActualTransformPos()` is the canonical example — it returns the inspector-assigned `actualPosition` if present, otherwise falls back to its own `transform`. Other interactables can opt in by exposing the same method shape.

```csharp
// ❌ WRONG — points at the collider's pivot, which may be off-screen / off-sprite.
TutorialManager.Instance.TryShowTutorial(
    TutorialManager.TutorialId.MyTutorial,
    startButton.transform,
    camera, forceClick: true, waitSeconds: -1f, Vector3.zero);

// ✅ RIGHT — uses the authored visual position when one is set, transform otherwise.
TutorialManager.Instance.TryShowTutorial(
    TutorialManager.TutorialId.MyTutorial,
    startButton.GetActualTransformPos(),
    camera, forceClick: true, waitSeconds: -1f, Vector3.zero);
```

**Apply this rule to every world-overload `TryShowTutorial` and `TryShowTutorialAnimatedPointer` call site.** Plain `Transform` references (e.g. `cloth.transform`) stay as-is; only switch when the target's type defines `GetActualTransformPos()`. Reference call site: `Washer.cs:191`.

---

## How `forcePlayerToClickFocus` Is Actually Enforced

Setting `forcePlayerToClickFocus: true` does **not** automatically block all input on its own. It sets `FocusBox._isForceClick = true`, exposed via `FocusBox.IsForceClickActive` and `FocusBox.ContainsScreenPoint(screenPoint)`.

**Input systems must opt in** by consulting the FocusBox. The canonical integration (copy this pattern in any new input-handling script) is at `Pickupable.cs:243-245`:

```csharp
var focusBox = TutorialManager.Instance.FocusBox;
if (focusBox.IsActive && !focusBox.ContainsScreenPoint(mousePos))
    return;  // Click is outside the highlighted area — swallow it.
```

**Action item when adding a new interactable:** if its input is meant to be gated during a tutorial, add the `FocusBox.IsActive && !FocusBox.ContainsScreenPoint(...)` guard to its input handler. Otherwise the highlight will be cosmetic only.

---

## Add a Tutorial: Step-by-Step

### Example Scenario
A new tool — **Baking Soda** — removes a new clothing condition — **Red Stains**. Player should learn this combo the first time they encounter a red stain AND have the tool.

### Step 1 — Add the Enum Value

Edit `TutorialManager.cs`:

```csharp
public enum TutorialId
{
    // …
    BakingSodaOnRedStainBeginner,
}
```

Pick a descriptive name. The convention in this codebase is `<Subject><Context>Beginner` (e.g., `LintToolBeginner`, `FoldingClothesBeginner`). Keep `Beginner` since that's the established suffix; it leaves room for `Intermediate` / `Advanced` tiers later.

### Step 2 — Create and Register the Asset

1. Right-click in `Assets/ScriptableObjects/Tutorials/` → **Create > CozySim > Tutorial > Tutorial**.
2. Name it `Tutorial_BakingSodaOnRedStainBeginner`.
3. Set `Id` = `BakingSodaOnRedStainBeginner`.
4. Fill `Text` with a ≤ 3-sentence instruction (e.g., *"Red stains are tough! Sprinkle baking soda on them before washing to break them down."*).
5. Leave `ShowPointer` = `true` unless the tutorial has no visual target.
6. Leave `Priority` = `0` unless this tutorial must win over a same-frame rival (see Priority section).
7. Drag the new asset into `TutorialManager.tutorialAssets` in the scene inspector.
8. **Save the scene.**

### Step 3 — Trigger from Gameplay Code

Trigger when the situation the tutorial teaches is first present. For our example, that's when a red stain is visible AND the player has baking soda available — trigger from whichever event happens later.

```csharp
// In RedStain.cs, RedStainSpawner.cs, or Inventory.cs — wherever the
// "player can now see a red stain and has the tool" condition resolves.
if (BakingSodaTool.IsUnlocked && stain.Type == StainType.Red)
{
    TutorialManager.Instance.TryShowTutorial(
        TutorialManager.TutorialId.BakingSodaOnRedStainBeginner,
        worldTarget: stain.transform,
        worldCamera: MinigameManager.Instance.MiniGameCamera,
        forcePlayerToClickFocus: true,
        waitSeconds: 0f,
        customPointerOffset: Vector3.zero
    );
}
```

**Safe to call repeatedly** — the manager short-circuits on FBPP key, global disable flag, or missing dictionary entry. You don't need a "has this shown yet" local flag.

### Step 4 — Mark Completed on Success

```csharp
// In BakingSodaTool.cs, at the moment the red stain is actually neutralized.
private void OnRedStainNeutralized()
{
    TutorialManager.Instance.MarkTutorialCompleted(
        TutorialManager.TutorialId.BakingSodaOnRedStainBeginner);
}
```

Don't complete the tutorial just because the player dismissed the text bubble — complete it when they *do the thing*. That way if they tap through without absorbing it, the tutorial returns next session for another chance.

### Step 5 — Test

1. Enter Play mode → reach the teachable situation → confirm bubble, focus box, pointer appear.
2. Tap/complete the action → confirm tutorial hides.
3. Re-enter the situation → confirm tutorial does **not** reappear (FBPP persistence working).
4. Call `TutorialManager.ClearAll()` from a debug hook → confirm it reappears next time.
5. If `forcePlayerToClickFocus: true`, confirm clicks outside the highlight box are ignored.

---

## Add Tutorials for a New Clothing Condition

Clothing conditions are things that can be "wrong" with a cloth: lint (existing: `ClothCondition.HasLint`), wrinkles, stains of various subtypes, holes, mud, etc. A new condition usually needs **at least two** tutorials:

- **Condition-recognition tutorial** — "this is what the new condition looks like," triggered on the first cloth that spawns with it.
- **Tool-application tutorial** — "this is how you fix it," triggered the first time the player holds the correct tool near the condition.

**Where to wire triggers:**

| Tutorial kind | Trigger site |
|---|---|
| Recognition | The spawner / factory that creates the cloth, or in `ClothCondition` right after the condition is applied |
| Tool application | The tool's `OnHoverOver` / `OnPickedUp` / minigame entry — wherever the tool-and-condition meet |
| Completion | The tool's *success* callback — where it mutates the cloth (e.g., `cloth.EraseLintAt` in `LintRoller.cs:83`) |

**Pattern example (from `LintRoller.cs` + `ToolTutorialBeats.cs`):**
- `ToolTutorialBeats.HandleItemPlaced` → `TryShowTutorial(LintRollerPickupBeginner, …)` when an item with lint is placed on the detailing table.
- `LintRoller.CompleteAndReturn` → `_beats.MarkComplete()` which marks both the pickup and usage ids done after a successful lint removal.

Mirror this structure for a new condition + tool pair.

---

## Add a Tutorial for a New Placement Zone

Placement zones (detailing table, washer, dryer, folding mat, etc.) are where the player moves cloth. A zone tutorial usually:

- Triggers the **first time a cloth is placed into the zone** (watch for the zone's placement event).
- Focuses on the zone itself or on the newly placed cloth.
- Uses **animated pointer** when the goal is "move this cloth from zone A to zone B" (e.g., animates from the cleaned shirt to the washer).

```csharp
// After cloth lands in the new zone for the first time:
TutorialManager.Instance.TryShowTutorialAnimatedPointer(
    TutorialManager.TutorialId.MyNewZoneBeginner,
    startTarget: placedCloth.transform,
    destinationTarget: targetZone.transform,
    worldCamera: MinigameManager.Instance.MiniGameCamera,
    forcePlayerToClickFocus: false,
    waitSeconds: 0.5f
);
```

---

## Add a Tutorial for a New Minigame

Minigames (like the washer cycle, sewing minigame, etc.) usually get a **welcome tutorial** on first entry and a **completion mark** on first success.

**Pattern (from `MinigameManager.cs:363`):**
```csharp
// On minigame start, before input is accepted
TutorialManager.Instance.TryShowTutorial(
    TutorialManager.TutorialId.MyMinigameBeginner,
    _items[0].GameObject.transform,   // focus on the first interactable
    miniGameCamera,
    true,                              // forcePlayerToClickFocus
    -1f,                               // immediate
    Vector3.zero);

// After the player wins their first run
TutorialManager.Instance.MarkTutorialCompleted(TutorialManager.TutorialId.MyMinigameBeginner);
```

**Fallback pattern:** see `WasherTutorialFallback.cs` — a dedicated MonoBehaviour that hosts the trigger so gameplay code stays clean. Use this when the minigame script would be cluttered by an inline call.

---

## Modify an Existing Tutorial

### Text only
Edit the `Text` field on the `TutorialManager` → `TutorialEntries` inspector entry. Save the scene. Done.

### Toggle pointer
Flip `Data.ShowPointer` on the entry.

### Change when it appears
Move (or duplicate) the `TryShowTutorial` call in gameplay code. Remove the old one.

### Change how it appears (UI → world, world → animated)
Change the overload at the call site. The manager doesn't care; it just forwards to `Tutorial.SetFocus` / `Tutorial.SetFocusAnimated`.

### Change the trigger condition
Wrap the `TryShowTutorial` call in the new guard. Remember: **do not add a "has been shown" local flag** — FBPP already gates this.

---

## Remove a Tutorial

1. Delete the `TryShowTutorial` and `MarkTutorialCompleted` calls from gameplay code.
2. Remove the asset from `TutorialManager.tutorialAssets` in the scene inspector (then delete the `.asset` file from `Assets/ScriptableObjects/Tutorials/`).
3. Remove the enum value from `TutorialId`.
4. (Optional) If players in the wild have the old FBPP key set, it becomes orphan data — harmless, not worth a migration.

Order matters: do (1) before (3) or the codebase won't compile between commits.

---

## Conditional Tutorials (failure-based, skill-based, etc.)

`TryShowTutorial` has no built-in condition hook — gate it yourself at the call site.

**Pattern: "show after N failures":**
```csharp
if (failCount >= 3)
{
    TutorialManager.Instance.TryShowTutorial(TutorialId.HardModeHint, hintPanel, false, -1f);
}
```

**Pattern: "one-shot per session, not persistent":**
Don't call `MarkTutorialCompleted` — FBPP is the only persistence, and `TryHideTutorial` on its own doesn't set the key. So the tutorial will return next session.

**Pattern: "return for another look until mastered":**
Only call `MarkTutorialCompleted` after N successes, not 1.

---

## API Reference

### `TutorialManager`

| Member | Purpose |
|---|---|
| `TryShowTutorial(TutorialId, RectTransform focus, bool forceClick, float waitSeconds)` | Show with UI focus. `focus` may be `null` for a bubble with no highlight. |
| `TryShowTutorial(TutorialId, Transform worldTarget, Camera worldCamera, bool forceClick, float waitSeconds, Vector3 customPointerOffset)` | Show with world focus. `customPointerOffset = Vector3.zero` → use FocusBox inspector default. |
| `TryShowTutorialAnimatedPointer(TutorialId, Transform start, Transform dest, Camera worldCamera, bool forceClick = false, float waitSeconds = -1f)` | Show with looping pointer between two world transforms. |
| `MarkTutorialCompleted(TutorialId)` | Set the FBPP key so it won't show again. |
| `IsTutorialCompleted(TutorialId)` | Returns `true` if the FBPP key is already set. Lets callers skip setup work when the tutorial would silently no-op. |
| `TryHideTutorial()` | Hide the current tutorial if active. Does **not** mark completed. Fires `OnHidden`. |
| `ClearAll()` | Delete every FBPP key for every `TutorialId` value. Debug/test use. Static method. |
| `IsTutorialActive` (getter) | `true` if the tutorial instance GameObject is active. |
| `CurrentTutorialId` (getter) | The `TutorialId?` currently on screen, or `null` if none. |
| `OnHidden` (static event) | Fires when a tutorial is dismissed via `TryHideTutorial`. Tools subscribe to retry pickup beats after a higher-priority tutorial completes. |
| `FocusBox` (field) | Public ref to the FocusBox so gameplay code can query `IsActive` / `ContainsScreenPoint` / `IsForceClickActive`. |

**`waitSeconds` semantics:**
- `< 0` (e.g., `-1f`) → show immediately, same frame.
- `= 0` → wait one frame via `StartCoroutine(… yield return null)`. Use this when the focus target is created the same frame (its position may not be valid yet).
- `> 0` → delay by that many seconds via `WaitForSeconds`.

**Return value:** `true` if the tutorial will be shown, `false` if globally disabled, already seen, or ID not in `TutorialEntries`.

### `FocusBox`

| Member | Purpose |
|---|---|
| `IsActive` | Is the FocusBox GameObject currently active. |
| `IsForceClickActive` | `IsActive && _isForceClick`. Input gates should consult this. |
| `ContainsScreenPoint(Vector2 screenPoint)` | Is the screen point inside the current highlight box? |
| `FocusOnRectTransform` / `FocusOnWorldTarget` / `FocusOnWorldTargetsAnimated` | Called by `Tutorial` — gameplay code should not call these directly. |
| `Hide()` | Called by `TutorialManager.TryHideTutorial` → `Tutorial.CompleteTutorial`. |

### `TutorialIdExtensions`

| Member | Purpose |
|---|---|
| `GetTutorialKey(this TutorialId)` | Returns `"Tutorial" + id.ToString()` — the FBPP key used for gating. |

---

## Testing Checklist

For every new or modified tutorial:

- [ ] Enum value added to `TutorialId`.
- [ ] Inspector entry added to `TutorialManager.TutorialEntries` (Id + Data filled).
- [ ] Scene saved.
- [ ] Trigger call added in gameplay code at the correct moment.
- [ ] Completion call added in gameplay code at the correct success moment.
- [ ] **First run:** tutorial appears, text readable, focus/pointer positioned correctly, no console errors.
- [ ] **After success:** tutorial hides and does not reappear on next trigger.
- [ ] **Next session (or post-`ClearTutorials`):** tutorial appears again.
- [ ] `forcePlayerToClickFocus: true` → input outside the highlight is ignored by the affected interactable (requires `ContainsScreenPoint` guard — verify it's in place).
- [ ] With `PlayerOptions.DisableTutorials = true` → tutorial does **not** appear and "Player has tutorials disabled!" is logged.
- [ ] No null-ref on any of: focus transform destroyed before display, camera missing, entry missing.

---

## Common Pitfalls

| Pitfall | Why | Fix |
|---|---|---|
| Tutorial appears every play session despite being "done" | Forgot `MarkTutorialCompleted` — FBPP key never set | Add the completion call at the success site |
| Tutorial never appears | Entry missing from `TutorialEntries`; id not in dict at `Awake`; global disable set | Check inspector entry exists; check `PlayerOptions.DisableTutorials` |
| Focus box wrong size / off-screen | World target has no `Renderer`/`SpriteRenderer` in children (FocusBox falls back to `Vector2.one * 100`); wrong camera passed | Ensure target has a renderer or pass the correct `worldCamera` |
| Pointer missing | `ShowPointer = false` on the entry; `FocusBox.Pointer` ref unassigned in scene | Toggle `ShowPointer`; inspect FocusBox |
| Click-through during `forcePlayerToClickFocus` | The receiving interactable doesn't consult `FocusBox.ContainsScreenPoint` | Add `Pickupable.cs:243-245` style guard to that interactable |
| Focus target created same frame → tutorial at wrong position | Position resolves before Unity finishes layout | Use `waitSeconds: 0f` (next frame) instead of `-1f` |
| Animated pointer stutters or doesn't loop | DOTween sequence interrupted by re-calling show; targets null | Avoid repeated calls while active; null-check both transforms |
| Forgot to drag the new asset into `TutorialManager.tutorialAssets` | Manager builds the dict at `Awake` from that list — asset on disk alone is invisible | Drag it in and save the scene |
| Pointer / focus box lands on the pivot, not the visible sprite | Passed `target.transform` when the type defines `GetActualTransformPos()` | Switch the call to `target.GetActualTransformPos()` (see *World-Target Convention*) |

---

## Invariants (Don't Violate These)

1. **One `TutorialId` = one `TutorialEntry` = one FBPP key.** Never reuse an id for a different purpose.
2. **The manager gates; callers don't.** Don't wrap `TryShowTutorial` in "has this run yet" booleans — FBPP already handles that, and local flags diverge across scenes.
3. **Trigger ≠ completion.** Showing a tutorial doesn't mark it done. Only `MarkTutorialCompleted` sets the FBPP key.
4. **Only one tutorial at a time.** `TryShowTutorial` calls `TryHideTutorial` first. Don't attempt to show two overlapping tutorials.
5. **FocusBox is shared.** There is a single `FocusBox` instance on `TutorialManager`. Don't instantiate another.
6. **Input gating is cooperative.** `forcePlayerToClickFocus: true` is a signal, not a mandate — only input handlers that consult `FocusBox.ContainsScreenPoint` will honor it.

---

## Quick Decision Tree

```
Q: What did the player just encounter / unlock / pick up?
├── A new UI element → UI-focus TryShowTutorial (RectTransform overload)
├── A new scene object (tool, cloth, zone, NPC) → World-focus TryShowTutorial (Transform overload)
├── A new multi-step workflow ("move X to Y") → TryShowTutorialAnimatedPointer
└── A story beat with no visual target → UI-focus with focus: null

Q: Where does completion belong?
├── Player performed the exact taught action → MarkTutorialCompleted at that call site
├── Player dismissed the bubble without doing it → nothing; let it return next session
└── Player achieved a general milestone that implies mastery → MarkTutorialCompleted in the milestone handler
```

---

## When to Escalate (Plan Mode / Human Review)

- Adding a tutorial that gates progression (forces completion before allowing gameplay to continue).
- Changing the persistence scheme (moving off FBPP, adding profiles, syncing across devices).
- Adding FocusBox modes (blur, multi-highlight, animated size changes).
- Adding tutorial chains (auto-advance from one tutorial to the next).
- Adding localization — `TutorialSO.Text` is currently a raw string; a loc layer is a system change, not a tutorial add.

---

## File Locations

- `Assets/_Scripts/UI/TutorialManager.cs`
- `Assets/_Scripts/UI/Tutorial.cs`
- `Assets/_Scripts/UI/FocusBox.cs`
- `Assets/_Scripts/UI/TutorialSO.cs`
- `Assets/_Scripts/UI/TutorialIdExtensions.cs`
- Tutorial content: inline on the `TutorialManager` GameObject in whatever scene hosts it (no assets on disk)
- Reference integrations: `LintRoller.cs`, `Iron.cs`, `Washer.cs`, `MinigameManager.cs`, `FoldableBase.cs`, `Pickupable.cs`, `WasherTutorialFallback.cs`
