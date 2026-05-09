# Nudge System Modifier Workflow

A comprehensive guide for extending the CozySim nudge system — the contextual pointer-hint system that guides players toward their next meaningful action during the laundry minigame.

---

## Quick Reference: What the Nudge System Does

The `NudgeManager` is a singleton that shows a contextual pointer hint when the player has been idle for `idleThresholdSeconds` (default 6s) of "no meaningful gameplay activity." 12 priority-ordered "nudge rules" evaluate the current gameplay state and pick the first one that matches.

- **Moving nudge**: A sprite tweens back and forth between two world targets (e.g., lint roller → shirt). Re-reads both target positions every loop iteration so it follows moving items.
- **Tapping nudge**: A sprite sits on top of a single world target (e.g., the washer start button). Follows the target in `LateUpdate`.

When the player takes a meaningful action, the idle timer resets and any active nudge hides. The system also re-evaluates on every loop so the pointer never lingers after the condition stops being true.

### Gating (when nudges are NOT shown)

From `NudgeManager.CanNudge()` (lines 193–198):
- `MinigameManager.Instance.IsActive == false` → no nudge (minigame not playable).
- `TutorialManager.Instance.IsTutorialActive == true` → no nudge (tutorials take precedence; the idle timer pauses, not resets).

There is no day-number gate in the current implementation — the plan originally had one but it was removed. If you need to re-add day gating, add a check against `DayManager.Instance.CurrentDayNumber` inside `CanNudge`.

---

## The Nudge System Architecture

### 1. Core Files (verified paths)

| File | Purpose |
|------|---------|
| `Assets/_Scripts/UI/NudgeManager.cs` | Main singleton; idle timer, evaluator, pointer animation loops |
| `Assets/_Scripts/Gameplay/Zones/PlacementZone.cs` | `OnItemPlaced` / `OnItemRemoved` events; `Items` read-only list; `ItemCount`; `IsLocked` flag |
| `Assets/_Scripts/Gameplay/Appliances/ApplianceBase.cs` | `OnCycleFinished` event; `IsRunning` property; `RunCycle` coroutine |
| `Assets/_Scripts/Gameplay/Appliances/Washer.cs` | `DetergentsUsed` list; stamps `"Washed"` / `"Detergent_Used"` tags |
| `Assets/_Scripts/Gameplay/Appliances/Dryer.cs` | `ActiveSettingIndex`, `SheetsUsed`; stamps `"Dryer_HighHeat"` on index ≥ 1 |
| `Assets/_Scripts/Gameplay/ClothCondition.cs` | `OnConditionChanged` event; `Dirtiness`, `Wetness`, `Crumple`, `Stain`, `HasLint`, `LintCount` |
| `Assets/_Scripts/Gameplay/Fold/FoldableBase.cs` | `IsFullyFolded`, `FirstActiveRegion`, `OnFoldAdvanced` UnityEvent |
| `Assets/_Scripts/Gameplay/Fold/FoldRegion.cs` | `RegionType` enum (ShirtLeftSleeve, ShirtRightSleeve, ShirtBottom, PantsLeg, PantsKnee) |
| `Assets/_Scripts/Gameplay/Minigame/MinigameManager.cs` | `IsActive`, `ActiveRuleSet` properties |
| `Assets/_Scripts/Gameplay/Tools/Pickupable.cs` | Static `OnAnyPickedUp` event; `PlacedInZone` property |
| `Assets/_Scripts/Gameplay/Tools/DraggableTool.cs` | Static `OnAnyToolUsed` event (fires each consume-attempt tick) |
| `Assets/_Scripts/Gameplay/GameplayTagContainer.cs` | `AddTag`/`HasTag` + `OnChanged` event; used for `"Washed"`, `"Detergent_Used"`, etc. |
| `Assets/_Scripts/Gameplay/ColliderButton.cs` | `OnClicked` UnityEvent — the wire point for appliance start buttons |
| `Assets/_Scripts/Gameplay/ObjectUnlocker.cs` | `gameObject.SetActive(owned)` — how tools appear after shop purchase |

### 2. Activity Signals That Reset the Idle Timer

`NudgeManager.RegisterActivity()` is called by:

| Signal | Source | NudgeManager subscription |
|--------|--------|---------------------------|
| Item placed in zone | `PlacementZone.OnItemPlaced` (Action\<Pickupable\>) | closure in `SubscribeToZone` (lines 134–140) |
| Item removed from zone | `PlacementZone.OnItemRemoved` (Action\<Pickupable\>) | same closure |
| Washer/dryer start button clicked | `ColliderButton.OnClicked` (UnityEvent) | lines 100–101 |
| Washer/dryer cycle finishes | `ApplianceBase.OnCycleFinished` (Action) | lines 102–103 |
| Any pickupable picked up | `Pickupable.OnAnyPickedUp` (static Action) | line 107 |
| Any draggable tool drags over target | `DraggableTool.OnAnyToolUsed` (static Action) | line 108 |
| Cloth condition changes | `ClothCondition.OnConditionChanged` (Action) | dynamically, via `HookCloth` (line 162) |
| Fold step advanced | `FoldableBase.OnFoldAdvanced` (UnityEvent) | dynamically, via `HookFoldable` (line 170) |

Cloth and foldable subscriptions are dynamic — hooked the first time an item enters a tracked zone (via `HandleItemEnteredZone`), cached in `_hookedConditions` / `_hookedFoldables` HashSets, and torn down wholesale in `OnDestroy`.

### 3. The 12 Nudge Rules (Priority Order)

Evaluated sequentially in `EvaluateNudge()` (NudgeManager lines 250–368). The first rule that matches wins — everything below it is skipped. Groupings:

- **Rules 1–3**: Detailing-table prep (lint, stains).
- **Rules 4–6**: Appliance interaction (washer detergent, washer start, dryer start).
- **Rules 7–9**: "Move cloth to the station it belongs at next" transitions.
- **Rules 10–12**: Folding table operations + final delivery.

| # | Match condition | Nudge | NudgeManager lines |
|---|-----------------|-------|--------------------|
| 1 | Cloth has lint AND NOT on detailing table AND (lint roller unlocked OR baking soda unlocked) | Moving: cloth → detailing table | 257–265 |
| 2 | Cloth on detailing table has lint AND lint roller assigned | Moving: lint roller → cloth | 268–270 |
| 3 | Cloth on detailing table has `StainType.Blood` or `StainType.Grease` AND baking soda unlocked | Moving: baking soda → cloth | 273–278 |
| 4 | Washer has items AND no detergent loaded AND detergent unlocked | Moving: detergent → washer | 283–287 |
| 5 | Washer has items AND not running AND cloth needs washing AND (detergent loaded OR order doesn't require detergent) | Tapping: washer start button | 294–304 |
| 6 | Dryer has items AND not running AND cloth needs drying | Tapping: dryer start button | 309–314 |
| 7 | Cloth needs washing (`!HasTag("Washed")`) AND NOT in washer | Moving: cloth → washer zone | 317–322 |
| 8 | Cloth needs drying (`Wetness > 0.01`) AND NOT in dryer | Moving: cloth → dryer zone | 325–330 |
| 9 | Cloth needs ironing (`Crumple > 0.01`) AND NOT on folding table | Moving: cloth → folding table zone | 333–338 |
| 10 | Cloth on folding table AND needs ironing AND iron assigned | Moving: iron → cloth | 341–346 |
| 11 | Cloth on folding table AND `!IsFullyFolded` | Tapping: `FoldableBase.FirstActiveRegion.transform` | 349–357 |
| 12 | Cloth is fully done (washed + dry + ironed + folded + no lint + `Stain == Normal`) AND NOT in out-basket | Moving: cloth → out-basket | 360–365 |

### 4. Zone Membership Tracking

`NudgeManager._zoneMembers` (lines 72–73) is a `Dictionary<PlacementZone, HashSet<Pickupable>>`. It is maintained by closure-captured handlers in `SubscribeToZone` (lines 134–140):

```csharp
zone.OnItemPlaced  += item => { if (item != null) _zoneMembers[zone].Add(item); HandleItemEnteredZone(item); };
zone.OnItemRemoved += item => { if (item != null) _zoneMembers[zone].Remove(item); HandleItemLeftZone(item); };
```

Why a parallel dictionary when `PlacementZone` already exposes `Items` (a public `IReadOnlyList<Transform>`)? Because the evaluator asks "is this specific `Pickupable` in this specific zone?" via `HashSet.Contains` (O(1)), while the `Items` list is a `Transform` list (requires GetComponent lookups per query) and is ordered/tweened for layout, not set-membership.

Two convenience enumerables sit on top:
- `ClothesInZone(zone)` (lines 424–433) — yields the `ClothCondition` of each tracked pickupable in the zone.
- `AllTrackedClothes()` (lines 435–439) — yields every `ClothCondition` ever hooked (scoped by lifetime of `_hookedConditions`). Used for "anywhere not in zone X" queries.

---

## How to Extend the Nudge System

### Scenario 1: Add a New Placement Zone (e.g., Dry-Hang Rack)

**Example goal**: add a clothesline zone where wet clothes can be passively dried by placing them there.

#### Step 1: Verify the zone exists in the scene
- Open `Assets/Prefabs/Minigame/MinigameRoot.prefab`.
- Confirm a GameObject under it has a `PlacementZone` (or subclass like `HorizontalZone` / `LayeredZone`) component.
- Optional: give it a descriptive `zoneId` like `"DryHangRack"` (used by systems that filter by id — the existing washer/dryer zones use an empty zoneId, so this is not strictly required).
- Confirm it has a `Collider2D` for item detection and its `acceptableTags` accept the cloth types you want.

#### Step 2: Wire the zone into NudgeManager
Add a serialized field to `NudgeManager.cs` under `[Header("Scene References — Zones")]`:

```csharp
[SerializeField] private PlacementZone dryHangZone;
```

Drag the zone reference in the Inspector.

#### Step 3: Subscribe in Start()
Find the `Start()` method (lines 87–109) and add `dryHangZone` to both the subscription loop and the `SubscribeToZone` calls:

```csharp
foreach (var z in new[] { inBasketZone, detailingTableZone, washerZone, dryerZone, foldingTableZone, outBasketZone, dryHangZone })
    if (z != null && !_zoneMembers.ContainsKey(z))
        _zoneMembers[z] = new HashSet<Pickupable>();

// ... after the existing SubscribeToZone calls ...
SubscribeToZone(dryHangZone);
```

#### Step 4: Add nudge rule(s) for the zone
The dry-hang rack is a valid drying destination, so rule 8 (clothes-need-drying not in dryer) must now also allow clothes in `dryHangZone`. Modify rule 8 in `EvaluateNudge()`:

```csharp
// 8. Clothes that need drying — treat BOTH the dryer and the dry-hang zone
// as valid drying destinations. Only nudge if the cloth isn't in either.
if (dryerZone != null)
{
    foreach (var cond in AllTrackedClothes())
        if (NeedsDrying(cond)
            && !IsClothInZone(cond, dryerZone)
            && !IsClothInZone(cond, dryHangZone))
            return NudgeDescriptor.Moving(cond.transform, dryerZone.transform);
}
```

If the dry-hang rack dries passively (no tool, no tap required), you do NOT need a corresponding "tap the dry-hang rack" rule — the cloth will just sit there and the `OnConditionChanged` event will fire when `Wetness` ticks down, resetting the idle timer. Once dry, the cloth naturally falls into rule 9 (move to folding table) or rule 12 (move to out-basket).

If it requires an active action (e.g. tap a "clip to line" button):
- Add a `[SerializeField] private ColliderButton dryHangActivateButton;` field.
- Subscribe `dryHangActivateButton.OnClicked.AddListener(OnActivityEvent);` in `Start()`.
- Insert a tapping rule alongside rule 6 (dryer start) gated on cloth presence and action-needed state.

#### Step 5: Test
- Place a wet cloth on the detailing table (or anywhere not in dryer/dry-hang). Idle 6+ seconds. Confirm the nudge points toward the dryer zone (unchanged priority).
- Move the cloth to the dry-hang rack. Confirm the nudge hides because the cloth is now in a valid drying destination.
- While drying passively, confirm nudges re-appear for other pending work (another cloth that needs washing, etc.).

---

### Scenario 2: Add a New Tool

**Example goal**: add a "Starch Spray" that removes `Crumple` and should be used on clothes sitting on the detailing table.

#### Step 1: Create the tool in the scene
- Model + root `Transform`.
- Add `Pickupable` + `DraggableTool` subclass (see `PulseTool` / `ClickPerUseTool` for bases) if it applies per-tick effects.
- If consumable, add a `Consumable` component. The existing `Consumable.RefillAllToFull()` call in `MinigameManager.Activate` will handle daily refill.
- If shop-unlocked, add `ObjectUnlocker` on the root — the tool's root `gameObject.activeInHierarchy` then becomes the "is unlocked?" check.

#### Step 2: Wire the tool into NudgeManager
Add a serialized field under `[Header("Scene References — Tools")]`:

```csharp
[SerializeField] private Transform starchSpray;
```

Drag the tool's root `Transform` in the Inspector (the root with `ObjectUnlocker`, NOT a sprite child).

#### Step 3: Pick a priority and add the rule
Think about workflow ordering:
- If the player should apply starch BEFORE the washer: insert as a new rule 1 or 2 (detailing-table-adjacent).
- If it should happen AFTER drying (like ironing): insert around rule 10.

For "use it on the detailing table before washing," insert a new rule that mirrors rules 1–3:

```csharp
// Rule X (insert between existing rules 2 and 3, shifting others down):
// Crumpled clothes on the detailing table — point starch spray at them if unlocked.
bool starchUnlocked = starchSpray != null && starchSpray.gameObject.activeInHierarchy;
if (starchUnlocked)
{
    foreach (var cond in ClothesInZone(detailingTableZone))
        if (cond.Crumple > 0.01f)
            return NudgeDescriptor.Moving(starchSpray, cond.transform);
}
```

The existing ironing rules (9 and 10) will still fire for any cloth that's still crumpled after starching — which is fine.

#### Step 4: Test
- Unlock starch spray (via the shop, or temporarily force `gameObject.SetActive(true)` on the tool).
- Place a crumpled shirt on the detailing table. Idle 6+ seconds → nudge points starch spray → shirt.
- Drag starch spray over the shirt. The `DraggableTool.OnAnyToolUsed` static event fires → timer resets → nudge hides.
- Crumple hits 0 via the tool's effect. On the next evaluation, rule skips because `Crumple <= 0.01`.
- Lock starch (`gameObject.SetActive(false)`). Confirm the rule silently skips and the next matching rule fires.

---

### Scenario 3: Add a New Clothing Condition

**Example goal**: track a new `Wrinkledness` state on `ClothCondition` that a new tool can remove.

#### Step 1: Add the property on ClothCondition
Add the backing field + property, making sure the setter calls `ApplyBlock()` (so `OnConditionChanged` fires):

```csharp
[SerializeField, Range(0f, 1f)] private float wrinkledness = 0f;

public float Wrinkledness
{
    get => wrinkledness;
    set { wrinkledness = Mathf.Clamp01(value); ApplyBlock(); }
}
```

Important: `ApplyBlock()` (lines 373–387 of `ClothCondition.cs`) fires `OnConditionChanged` at the end, so any tool that writes to this property automatically resets the idle timer.

#### Step 2: Add a helper on NudgeManager
Next to the existing helpers (`NeedsDrying`, `NeedsIroning`):

```csharp
private bool NeedsWrinkleRemoval(ClothCondition c) => c != null && c.Wrinkledness > 0.01f;
```

#### Step 3: Update `IsReadyForDelivery` if applicable
If a wrinkled cloth should block final delivery, add the check in `IsReadyForDelivery` (lines 412–422):

```csharp
if (c.Wrinkledness > 0.01f) return false;
```

#### Step 4: Add a nudge rule
Insert at the appropriate priority, gated on your tool being unlocked (same pattern as baking soda, rule 3):

```csharp
bool wrinkleRemoverUnlocked = wrinkleRemover != null && wrinkleRemover.gameObject.activeInHierarchy;
if (wrinkleRemoverUnlocked)
{
    foreach (var cond in ClothesInZone(detailingTableZone))
        if (NeedsWrinkleRemoval(cond))
            return NudgeDescriptor.Moving(wrinkleRemover, cond.transform);
}
```

---

### Scenario 4: Add a New Appliance

**Example goal**: a "Scenter" machine that marks clothes with a `"Scented"` gameplay tag and has its own placement zone + start button.

#### Step 1: Create the appliance class
Inherit from `ApplianceBase` (gives you the cycle coroutine, `OnCycleFinished` event, `IsRunning` property, cycle animations, and start-button plumbing for free).

```csharp
using UnityEngine;

public class Scenter : ApplianceBase
{
    protected override void ProcessItem(Collider2D hit)
    {
        hit.GetComponentInParent<GameplayTagContainer>()?.AddTag("Scented");
    }
}
```

#### Step 2: Create the scene hierarchy
- Scenter root with `Scenter` component. Wire `placementZone`, `placementZoneCollider`, `startButton`, and `bodyRenderer` in the Inspector (inherited from `ApplianceBase`).
- `PlacementZone` child (likely a subclass) as the drum.
- `ColliderButton` child as the start button.

#### Step 3: Wire into NudgeManager
```csharp
[Header("Scene References — Appliances")]
[SerializeField] private Scenter scenter;
[SerializeField] private ColliderButton scenterStartButton;

[Header("Scene References — Zones")]
[SerializeField] private PlacementZone scenterZone;
```

In `Start()`:
```csharp
// Track zone membership for scenter
if (scenterZone != null && !_zoneMembers.ContainsKey(scenterZone))
    _zoneMembers[scenterZone] = new HashSet<Pickupable>();
SubscribeToZone(scenterZone);

// Reset the idle timer on button press and cycle completion
if (scenterStartButton != null) scenterStartButton.OnClicked.AddListener(OnActivityEvent);
if (scenter != null) scenter.OnCycleFinished += OnActivityEvent;
```

In `OnDestroy()`, add the teardown for the new subscriptions (closure-captured zone subscriptions are NOT un-subscribed — only the ones with named handlers):
```csharp
if (scenterStartButton != null) scenterStartButton.OnClicked.RemoveListener(OnActivityEvent);
if (scenter != null) scenter.OnCycleFinished -= OnActivityEvent;
```

#### Step 4: Add nudge rule
Decide where in the priority list this belongs. For a "should scent things that have been washed and dried," insert between rule 8 (drying) and rule 9 (ironing):

```csharp
// New rule: Clothes in scenter that don't yet have the "Scented" tag.
if (scenter != null && !scenter.IsRunning && scenterZone != null && scenterZone.ItemCount > 0 && scenterStartButton != null)
{
    foreach (var cond in ClothesInZone(scenterZone))
    {
        var tags = cond.GetComponent<GameplayTagContainer>();
        if (tags != null && !tags.HasTag("Scented"))
            return NudgeDescriptor.Tapping(scenterStartButton.transform);
    }
}
```

If a scented cloth should also block delivery, gate the `IsReadyForDelivery` check on `GameplayTagContainer.HasTag("Scented")` when the current order requires it. See `OrderRequiresDetergent()` (lines 386–400) for a template.

---

### Scenario 5: Change Rule Priority

**Example goal**: "fold clothes BEFORE they go in the dryer — don't suggest drying until after folding."

1. Open `EvaluateNudge()` (lines 250–368).
2. Find rules 8 (drying transition) and 9–11 (folding table workflows).
3. Cut the folding-table block and paste it above the drying block.
4. Update the rule-number comments so they stay sequential and document what you changed.
5. Test all three: dry clothes should nudge to folding table first (if crumpled), then only get the dryer nudge if they're dry but wrinkled elsewhere.

Priority changes are cheap — the rules are independent — but they can ripple. Always re-run the full manual test matrix after a priority change.

---

### Scenario 6: Add Tag-Based Nudge Gating

**Example goal**: "Only nudge to apply detergent if the current order actually rewards detergent use."

See the existing `OrderRequiresDetergent()` helper (lines 386–400) for the pattern. It walks `MinigameManager.Instance.ActiveRuleSet.Rules`, looks for an `ActionTagRule` with a specific `ActionTag`, and returns whether it's present. Rule 5 (line 297) uses it to avoid nagging about detergent when the order doesn't care.

To add a similar gate for another tag:

```csharp
private bool OrderRequiresScenter()
{
    var ruleSet = MinigameManager.Instance?.ActiveRuleSet;
    if (ruleSet == null) return false;
    foreach (var rule in ruleSet.Rules)
    {
        if (rule is ActionTagRule action
            && action.Trigger == TagRuleSO.TriggerType.OnMet
            && action.ActionTag == "Scented")
            return true;
    }
    return false;
}
```

Use inside a rule to skip nudging when the tag isn't order-relevant.

---

## Common Patterns & Code Conventions

### Pattern 1: Unlock-Gated Rules

```csharp
bool toolUnlocked = toolTransform != null && toolTransform.gameObject.activeInHierarchy;
if (toolUnlocked) { /* ... rule body ... */ }
```

Works because `ObjectUnlocker.ApplyState()` (in `ObjectUnlocker.cs`) calls `gameObject.SetActive(owned)`. `activeInHierarchy` (not `activeSelf`) is correct here because an unlocked tool nested under a disabled parent should still be considered "not usable."

### Pattern 2: "Clothes In Zone" Query

```csharp
foreach (var cond in ClothesInZone(someZone))
{
    // cond is a ClothCondition on a Pickupable in that zone
}
```

Lines 424–433. Iterates `_zoneMembers[zone]` HashSet. Skips null/destroyed entries. Safe to use in every rule.

### Pattern 3: "All Tracked Clothes" Query

```csharp
foreach (var cond in AllTrackedClothes())
{
    if (!IsClothInZone(cond, someZone)) { /* ... */ }
}
```

Lines 435–439. Iterates `_hookedConditions` HashSet. Only includes clothes that have ever entered a tracked zone during this minigame — clothes just spawned into a non-tracked area won't appear. In practice every cloth spawns in the in-basket, so this is effectively "every cloth in the minigame."

### Pattern 4: Zone Subscription via Closure

```csharp
private void SubscribeToZone(PlacementZone zone)
{
    if (zone == null) return;
    zone.OnItemPlaced  += item => { if (item != null) _zoneMembers[zone].Add(item);    HandleItemEnteredZone(item); };
    zone.OnItemRemoved += item => { if (item != null) _zoneMembers[zone].Remove(item); HandleItemLeftZone(item); };
}
```

Lines 134–140. The closure captures `zone` so the handler knows which set to touch — `PlacementZone.OnItemPlaced` only passes the `Pickupable`, not the zone. Trade-off: these lambdas cannot be cleanly unsubscribed in `OnDestroy`, so NudgeManager relies on scene teardown to reclaim them. Do not copy this pattern to managers that persist across scenes.

### Pattern 5: Condition-Helper Methods

```csharp
private bool NeedsWashing(ClothCondition c)  { /* has GameplayTagContainer + !HasTag("Washed") */ }
private bool NeedsDrying(ClothCondition c)   => c != null && c.Wetness > 0.01f;
private bool NeedsIroning(ClothCondition c)  => c != null && c.Crumple > 0.01f;
private bool NeedsFolding(ClothCondition c)  { /* has FoldableBase + !IsFullyFolded */ }
private bool IsReadyForDelivery(ClothCondition c) { /* AND of all the above false + no lint + no stain */ }
```

Centralizes "what does it mean to need X?" so rules stay readable AND changing the definition in one place propagates to every rule that uses it.

### Pattern 6: Cycle-Running Guard on Tapping Rules

```csharp
if (appliance != null && !appliance.IsRunning && /* ... */)
{
    return NudgeDescriptor.Tapping(startButton.transform);
}
```

Rules 5 and 6 (lines 294 and 309) demonstrate this — `ColliderButton` is already disabled during a cycle, so suggesting a tap that can't succeed would be misleading.

### Pattern 7: GameplayTagContainer as the Wash/Action Marker

Rather than tracking "has this been washed?" on `ClothCondition`, CozySim uses `GameplayTagContainer` tags that are stamped at the moment an action succeeds:

- `"Washed"` — stamped by `Washer.ProcessItem` (line 94) at cycle end.
- `"Detergent_Used"` — stamped same line (line 95) if detergents were loaded.
- `"Dryer_HighHeat"` — stamped by `Dryer.ProcessItem` (line 166) when `ActiveSettingIndex >= 1`.
- `"ChemicalSpray_Used"` — stamped by `ChemicalSpray.cs` on hit.
- `"BleachSafe"` — authored in the Inspector as an exemption tag.

For a nudge that asks "has this action been performed?", prefer `tags.HasTag("MyTag")` over inventing a new boolean flag on `ClothCondition`. Action tags also power the scoring system (`OrderEvaluator` / `ActionTagRule`), so reusing them keeps the model cohesive.

---

## Debugging & Testing New Rules

### Debug Menu: Force a Nudge

In the Unity editor, right-click the `NudgeManager` component → **"Debug / Force moving nudge (first two scene SpriteRenderers)"** (lines 564–569). Uses the first two SpriteRenderers in the scene as endpoints. Useful for verifying the pointer animation loops and that your prefab wiring works before adding any real rules.

### Debug Logs

`TryShowNudge` already logs when a nudge starts (lines 217, 223):
```csharp
Debug.Log("Showing moving nudge: " + nudge.ToDebugString());
Debug.Log("Showing tap nudge: "    + nudge.ToDebugString());
```

`ToDebugString()` (line 244) prints Kind/Start/End. If a new rule isn't firing, check this log first — if it never logs, the rule didn't match; if it logs a different nudge, a higher-priority rule is winning.

### Step-by-Step Test Checklist for a New Rule

1. **Pre-reqs**: Tool/zone/appliance exists in the scene, wired in NudgeManager Inspector.
2. **Matching state**: Set up the scene so *only* your rule should match (put clothes where needed, nothing else pending).
3. **Idle**: Wait `idleThresholdSeconds`. The nudge should appear.
4. **Correct endpoints**: For moving nudges, both start and end targets should look right. For tapping, the pointer sits on the target.
5. **Follows moving targets**: Drag a target mid-animation. On the next loop iteration (≤ `pointerTravelDuration + pointerLoopDelay`), the pointer should re-fetch positions.
6. **Hides on action**: Perform the action the nudge hints at. Confirm the nudge disappears within one loop (for moving) or one `LateUpdate` (for tapping).
7. **Priority**: Create a state where two rules match (your new one + an existing higher-priority rule). Confirm the higher-priority rule wins.
8. **Null tolerance**: Unassign one of the new Inspector references. Confirm `EvaluateNudge` doesn't throw — the `!= null` guards should be defensive on every new field.
9. **Tutorial interop**: Fire a tutorial (`TutorialManager.Instance.TryShowTutorial(...)`). Confirm the nudge hides and the idle timer pauses (so the moment the tutorial ends, you don't get an immediate nudge-spam).
10. **Minigame-inactive**: After end-of-order, `MinigameManager.IsActive` becomes false. Confirm no stray nudges appear on the home/reception scene.

### Performance Notes

- `EvaluateNudge` runs on every idle-timer trip, on every moving-loop iteration (~every 2s), and every `LateUpdate` while a tapping nudge is active.
- Cost is `O(zones × members + tracked-cloth-count)`. With 5–10 clothes, negligible.
- If you add a rule that calls `GetComponent<T>()` inside a nested loop, cache the lookup on the cloth instead. The helpers (`NeedsFolding`, `IsClothInZone`) already do `GetComponent` once per iteration — don't double it.

---

## Edge Cases & Gotchas

### 1. Closure Subscriptions Leak on Scene Reload

`SubscribeToZone` uses lambdas. Because they're never stored, `OnDestroy` can't call `-=` on them. Acceptable because the `PlacementZone` itself dies when the scene reloads. Do not reuse this pattern in managers that outlive the scene.

### 2. `activeInHierarchy` vs `activeSelf`

Always use `activeInHierarchy` for unlock checks. A tool under a disabled "Tools" parent should be treated as unlocked-but-offscreen only if you genuinely want that; normally you want both conditions to mean "available."

### 3. Null-Assignment Tolerance

Every field should be treated as possibly-null in `EvaluateNudge`. If someone forgets to wire the Inspector reference, the rule should silently skip rather than throw. Example:

```csharp
if (washer != null && washerZone != null && washerStartButton != null && ...)
```

### 4. `PlacedInZone` is Assigned by PlacementZone

`Pickupable.PlacedInZone` is a read-mostly property (`PlacementZone` writes it in `TryPlace` / `Remove`). Never set it directly from a nudge rule — use it to check state only.

### 5. Per-Loop Re-Evaluation Can Swap Nudge Type

Inside `MovingPointerLoop` (lines 523–559) and `LateUpdate` tapping branch (lines 493–515), `EvaluateNudge` runs again each iteration. If the winning nudge has changed type or endpoints, the code dispatches the new nudge and exits. Rules should be idempotent — calling them repeatedly with the same state must return the same result.

### 6. Rule-5 "Detergent Loaded" is Conditional

Rule 5 (lines 294–304) does NOT require detergent to be loaded unless the active order actually rewards it (`OrderRequiresDetergent` check). Without this, the nudge would demand detergent even on orders that penalize it. If you add a similar "consumable" tool (e.g. dryer sheets), follow the same pattern — check the order's `ActiveRuleSet` before nagging.

### 7. Rule 1 Unlock Gate Is Either-Or

Rule 1 (lines 257–265) fires if EITHER the lint roller OR baking soda is unlocked. This is because the detailing table is shared across both tools and either tool's presence justifies moving clothes there. If you add another detailing-table tool (like starch), include it in that `OR` or update the gate accordingly.

### 8. Idle-Timer Pause (Not Reset) During Tutorials

Look at `Update()` (lines 175–191): when `CanNudge()` returns false during a tutorial, the method returns early without touching `_idleTimer`. When the tutorial ends, the timer resumes accumulating. This prevents "nudge pops up instantly after a 10-second tutorial" but also means a tutorial doesn't *reset* the player's recent activity. If you want a tutorial to reset the timer, call `RegisterActivity()` from `TutorialManager`'s completion hook.

### 9. `activeKind != None` Early-Out in Update

In `Update()` (line 189), once a nudge is active, the idle timer keeps incrementing but `TryShowNudge` is skipped. The active nudge's own per-loop re-evaluation handles swaps/hides. A fresh nudge will only fire via `TryShowNudge` if the previous one hid itself and the timer reaches the threshold again.

---

## File Checklist for Adding an Extension

When adding anything, verify:

- [ ] `NudgeManager.cs`: serialized field(s) added under the right `[Header]`.
- [ ] `NudgeManager.Start()`: new subscriptions (button listeners, `OnCycleFinished`, zone subscriptions).
- [ ] `NudgeManager.OnDestroy()`: matching `-=` / `RemoveListener` for any non-closure subscription.
- [ ] `_zoneMembers` dictionary: contains an entry for each new tracked zone.
- [ ] `EvaluateNudge()`: new rule(s) inserted at the correct priority, with null guards on every field.
- [ ] Helper methods: added or updated (`NeedsX`, `IsReadyForDelivery`).
- [ ] Scene Inspector: every new serialized field has a reference assigned.
- [ ] Manual test matrix: ran the 10-step checklist above.

---

## Complexity Summary

| Task | Files Changed | Estimated Effort |
|------|---------------|------------------|
| Change rule priority | `NudgeManager.cs` | Trivial (5 min) |
| Add a tool with a new rule | `NudgeManager.cs` + scene wiring | Low (15–30 min) |
| Add a placement zone | `NudgeManager.cs` + scene wiring | Low (15–30 min) |
| Add a new clothing condition | `ClothCondition.cs` + `NudgeManager.cs` | Medium (1 hour) |
| Add a new appliance | New class + `NudgeManager.cs` + scene setup | Medium (1–2 hours) |
| Add a new GameplayTag marker | `<source>.cs` stamps tag, `NudgeManager.cs` reads | Low (20 min) |
| Add order-driven nudge gating | New helper + rule in `NudgeManager.cs` | Low (30 min) |

The nudge system is **designed for extension**: rules are independent, every reference is null-safe, the activity signals cover most meaningful state changes without new events, and the per-loop re-evaluation guarantees no stale nudges.

---

## References

- Main implementation: `Assets/_Scripts/UI/NudgeManager.cs`
- Implementation plan: `thoughts/shared/plans/claude-plan-nudge-monobehaviour.md`
- Prefab zone IDs (in `Assets/Prefabs/Minigame/MinigameRoot.prefab`): `"DetailingTable"`, `"FoldingTable"`, `"InBasket"`, `"OutBasket"`. Washer and dryer zones have empty `zoneId` and must be referenced directly.
- Known tags in use: `"Washed"`, `"Detergent_Used"`, `"Dryer_HighHeat"`, `"ChemicalSpray_Used"`, `"BleachSafe"`.
