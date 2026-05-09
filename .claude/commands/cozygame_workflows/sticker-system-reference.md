---
description: Quick reference for the laundering minigame sticker system — files, prefabs, addressables, and runtime flow. Use when adding new variants, tweaking peel rewards, or extending sticker behaviour.
---

# Sticker System Reference

A quick-reference guide for CozySim's per-cloth sticker system: where the code lives, how the spawn/peel pipeline works, and what assets are wired together.

---

## Quick Reference: What the Sticker System Does

Stickers are decorative GameObjects parented to cloth items during the laundering minigame's spawn step. While a cloth is on the **detailing table**, the player can left-click a sticker to "peel" it: the sticker GameObject deactivates, a log is emitted, and a per-peel reward (currently `$0.10` / `10` cents) is credited to a day-scoped HUD bucket. At end-of-day, all peels coalesce into one **"Sticker Peels (xN)"** row in the Results popup.

Two variants exist:
- **RandomImage** — `SpriteRenderer` sprite chosen at random from an Addressables-loaded library
- **HelloIAm** — `SpriteRenderer` background (one of two badge images) + `TextMeshPro` 3D text overlay with a random first name

Both variants share the same `Sticker.cs` MonoBehaviour and click-gate logic.

---

## Core Files

| File | Purpose |
|------|---------|
| `Assets/_Scripts/Gameplay/Sticker.cs` | The MonoBehaviour on every sticker GameObject — variant config, click gate, peel logic |
| `Assets/_Scripts/Gameplay/StickerLibrary.cs` | Static class: preloads `stickers-random` Addressables label into `IReadOnlyList<Sprite> Random` |
| `Assets/_Scripts/Gameplay/StickerNames.cs` | Static class: 15-name pool for HelloIAm name overlay; `GetRandom()` |
| `Assets/_Scripts/Gameplay/ClothCondition.cs` | Owns `StickerCount` property (range 0–5) and `MaxStickerCount` const |
| `Assets/_Scripts/Gameplay/Minigame/MinigameSettings.cs` | `ClothingItem.overrideStickers` field (-1 = random, 0–5 = override) |
| `Assets/_Scripts/Gameplay/Minigame/MinigameManager.cs` | Sticker prefab serialized fields, `SpawnStickers()` helper, `GetRandomStickerAmount()`, `DetailingTableZone` getter, spawn-time wiring in `Activate` loop |
| `Assets/_Scripts/Gameplay/Tools/Pickupable.cs` | Pickup blocker plumbing + `MeshRenderer` sort-order plumbing for HelloIAm TMP text |
| `Assets/_Scripts/UI/HUD/HUDManager.cs` | `_dayStickerPeelCount` / `_dayStickerCents` buckets, `AddStickerPeel(int cents)`, reset in `ClearDayRevenue()` |
| `Assets/_Scripts/UI/Popups/Results/ResultsPopup.cs` | `PopulateAdjustments` renders the coalesced "Sticker Peels (xN)" row above the Supplies Used row |
| `Assets/_Scripts/Bootstrapper.cs` | `Start()` is a coroutine that yields on `StickerLibrary.EnsureLoaded()` before scene load |

---

## Prefabs & Assets

| Path | Purpose |
|------|---------|
| `Assets/Prefabs/Stickers/Sticker_RandomSticker.prefab` | Root: `Sticker` (variant=RandomImage) + `SpriteRenderer` (sortingOrder 41) + `BoxCollider2D`. Sprite assigned at spawn from `StickerLibrary.Random`. |
| `Assets/Prefabs/Stickers/Sticker_HelloIAm.prefab` | Root: `Sticker` (variant=HelloIAm) + `SpriteRenderer` (sortingOrder 41) + `BoxCollider2D`. Child `NameText` with `TextMeshPro` (3D / MeshRenderer, sortingOrder 42) overlay. Sticker orders sit just above the parent shirt (`Pickupable.HeldSortingOrder = 40`) so they always render on top. |
| `Assets/Textures/Stickers/HelloIAm/Hello_I_Am.png` | Default HelloIAm badge background (white) |
| `Assets/Textures/Stickers/HelloIAm/Hello_I_Am_blue.png` | Alternate HelloIAm badge background (blue) |
| `Assets/Textures/Stickers/RandomStickers/` | Folder of sprites loaded by Addressables label `stickers-random` |
| `Assets/AddressableAssetsData/` | Addressables settings + group definitions (`Stickers` group) |

### Addressables wiring

- Group: `Stickers` (Packed Assets)
- Label: `stickers-random` — assigned to entries inside `Assets/Textures/Stickers/RandomStickers/`
- The HelloIAm backgrounds (`Hello_I_Am.png`, `Hello_I_Am_blue.png`) are **direct prefab references** on `MinigameManager.helloIAmBackgrounds`, **not** Addressable.

### Scene wiring (on `MinigameManager` in the laundering scene)

| Inspector field | Assigned value |
|-----------------|----------------|
| `randomStickerPrefab` | `RandomImageSticker.prefab` |
| `helloIAmStickerPrefab` | `HelloIAmSticker.prefab` |
| `helloIAmBackgrounds[0]` | `Hello_I_Am.png` |
| `helloIAmBackgrounds[1]` | `Hello_I_Am_blue.png` |
| `detailingTableZone` | The detailing-table `PlacementZone` in the scene |

---

## Runtime Flow

### 1. Boot — preload the library
`Bootstrapper.Start()` is an `IEnumerator` that yields on `StickerLibrary.EnsureLoaded()` before calling `SceneLoader.LoadScene(s_startingScene)`. This guarantees `StickerLibrary.Random` is populated (or has been logged-warned as empty) before any scene that uses stickers loads.

`StickerLibrary.EnsureLoaded(label = "stickers-random")` calls `Addressables.LoadAssetsAsync<Sprite>(label, callback)` and yields on the handle. On failure it logs a warning but does not throw — the system **gracefully degrades** to no random stickers spawning.

### 2. Spawn — per-cloth child instantiation
In `MinigameManager.Activate(MinigameSettings)`, the per-item loop (just after `condition.InitializeLintMask()`):
```csharp
condition.StickerCount = itemSetting.overrideStickers >= 0
    ? itemSetting.overrideStickers
    : GetRandomStickerAmount();   // Random.Range(0, 3)
SpawnStickers(condition, clothingItem.transform);
```
`SpawnStickers` loops `StickerCount` times and for each iteration:
1. Coin flip (`Random.value < 0.5f`) chooses HelloIAm vs RandomImage. HelloIAm is only chosen when `helloIAmStickerPrefab != null`.
2. `Instantiate(prefab, clothTransform)` — the sticker becomes a **child of the cloth GameObject**.
3. Configures the variant via `ConfigureRandomImage(sprite)` or `ConfigureHelloIAm(background, name)`. If `StickerLibrary.Random` is empty for the random branch, that iteration `continue`s and skips — no error.

### 3. Peel — click gate
`Sticker.Update()` runs every frame on every spawned sticker. Early-out chain (in order):
1. `Mouse.current.leftButton.wasPressedThisFrame` — only act on press
2. `Pickupable.IsAnyHeld` — never peel while something is held
3. Parent's `PlacedInZone == MinigameManager.Instance.DetailingTableZone` — must be on the detailing table
4. `zone.IsLocked` — appliances/zones can suppress
5. `UIHelpers.IsMouseOverBlockingUI()` — UI takes precedence
6. `TutorialManager.Instance.FocusBox` gating — when active, the click must be inside the focus box
7. `_collider.OverlapPoint(worldPos)` — the click must hit this sticker's collider

If all pass, `Peel()` is called.

### 4. Peel — the action itself
```csharp
private void Peel()
{
    _stickerPeelClaimedFrame = Time.frameCount;
    gameObject.SetActive(false);
    Debug.Log($"[Sticker] peeled {_variant} from {_parentPickupable?.name}");
    HUDManager.Instance.AddStickerPeel(RewardCents);   // RewardCents = 10
}
```
The static `_stickerPeelClaimedFrame` field is the **same-frame pickup blocker**: in `Sticker.Awake()`, every sticker registers a pickup blocker on its parent `Pickupable` that returns `true` iff `_stickerPeelClaimedFrame == Time.frameCount`. So clicking a sticker can never also pick up the cloth on that same click. (Frame-stamp pattern, not a flag — works across all sticker instances and resets implicitly next frame.)

### 5. Reward bookkeeping
`HUDManager.AddStickerPeel(int cents)`:
- Increments `_dayStickerPeelCount`
- Adds to `_dayStickerCents`, `_totalCents`, `_dayCents`, `_totalAdjustmentCents`, `_dayAdjustmentCents`
- Calls `RefreshMoneyText()`

`HUDManager.ClearDayRevenue()` (called at start of each day) zeroes the two sticker buckets along with the rest.

### 6. Results popup row
`ResultsPopup.PopulateAdjustments(adjustments, toolUsageCostCents, stickerPeelCount, stickerCents)` renders rows in this order:
1. One row per `RuleAdjustment` in `adjustments`
2. **"Sticker Peels (xN)"** row (if `stickerCents > 0`) — N is the count, value is the total cents
3. **"Supplies Used"** row (if `toolUsageCostCents > 0`) — negative

The reveal animation in `BuildRevealRows` includes the sticker row automatically because it iterates active children of `adjustmentEntriesRoot`.

---

## Sort-Order Plumbing (HelloIAm specifics)

The HelloIAm variant uses a `TextMeshPro` 3D component (not `TextMeshProUGUI`) so its text renders via a `MeshRenderer` rather than a `SpriteRenderer`. To make held-cloth sort ordering work for the TMP overlay, `Pickupable.cs` was extended to:

- Cache `MeshRenderer[] _meshRenderers` in `Awake` (`GetComponentsInChildren<MeshRenderer>(true)`)
- Snapshot their `sortingOrder` values in **both** branches of `TryPickUp` (with-pre-placement-state and without)
- Loop over them in both `BoostSortingOrder()` (set to `HeldSortingOrder = 40`) and `RestoreSortingOrder()` (restore from snapshot)

If you add another sticker variant that uses any non-`SpriteRenderer` renderer, this plumbing already covers it as long as it's a `MeshRenderer` subtype. For other renderer types, extend the same pattern in `Pickupable`.

---

## Common Tweaks

### Change the per-peel reward
`Sticker.cs` → `private const int RewardCents = 10;`

### Change the random count range
`MinigameManager.cs` → `public static int GetRandomStickerAmount() => Random.Range(0, 3);` (currently 0–2 inclusive)

### Change the max sticker cap per cloth
`ClothCondition.cs` → `private const int MaxStickerCount = 5;`

### Override sticker count per cloth in a minigame setting
On the `MinigameSettings.ClothingItem` in the inspector: set `overrideStickers` to `0`–`5`. Leave at `-1` (default) for random.

### Add a new HelloIAm name
`StickerNames.cs` → add to the `_all` array.

### Add a new HelloIAm background
Drop the sprite into the project, then assign it as a new entry in `MinigameManager.helloIAmBackgrounds[]` in the inspector. The spawn picks uniformly at random from this array.

### Add a new RandomImage sprite
Drop the sprite into `Assets/Textures/Stickers/RandomStickers/`. With folder-as-Addressable-entry it's auto-included in the `stickers-random` label. With per-asset entries, mark it Addressable and assign the label.

### Change which zone is "peelable"
`Sticker.Update()` checks `zone == MinigameManager.Instance.DetailingTableZone`. To allow peeling from another zone, swap the check or extend with an OR. To allow from any zone, drop the zone-equality check and keep only the `zone != null` + `IsLocked` checks.

### Add a new variant
1. Add to the `Variant` enum in `Sticker.cs`
2. Add a `ConfigureXxx(...)` method to `Sticker.cs` for variant-specific config
3. Add a serialized prefab field on `MinigameManager`
4. Extend `SpawnStickers` to choose the new variant (rebalance the coin flip or add a third branch)

---

## What the Sticker System Does NOT Do

These were explicit non-goals in the original plan; do not assume they exist:

- ❌ No localization of HelloIAm names
- ❌ No sticker-specific tutorials or nudges
- ❌ No re-application of stickers after peel (peeled = gone for the run)
- ❌ No persistent sticker collection across runs
- ❌ No `OrderEvaluator` / tag-rule integration (peeling does not affect order satisfaction)
- ❌ No stickers on items other than shirts/pants (driven by `MinigameSettings.ClothingItem.Type`)
- ❌ No audio/VFX on peel
- ❌ No per-variant reward differentiation (both variants pay `RewardCents`)

---

## Gotchas

- **`StickerLibrary.Random` may be empty.** The Addressables label may have zero assets, or load may have failed (check console for `[StickerLibrary] Failed to load label 'stickers-random'`). `SpawnStickers` silently `continue`s in this case — random stickers just don't spawn. HelloIAm still does.
- **`Camera.main` is captured in `Awake`.** If the main camera changes after sticker spawn, the world-point hit test will be stale. Not currently an issue in the laundering scene, but worth knowing.
- **The pickup blocker is a static frame-stamp**, not per-instance state. This is intentional: clicking *any* sticker on a cloth blocks pickup of that cloth (and every other cloth) for that frame. Since only one sticker can be peeled per click anyway, the cross-instance interference is benign.
- **`HUDManager.AddStickerPeel` writes to `_dayAdjustmentCents` and `_totalAdjustmentCents`.** That means sticker cents already roll into `DayAdjustmentCents` for `DayBaseRevenueCents = _dayCents - _dayTipsCents - _dayAdjustmentCents`. The sticker row in Results is purely cosmetic separation; the math is already consistent.
- **Bootstrapper.Start blocks scene load on the Addressables fetch.** First-run load time depends on label size. If the label ever grows large, consider preloading async-in-background instead of blocking.
