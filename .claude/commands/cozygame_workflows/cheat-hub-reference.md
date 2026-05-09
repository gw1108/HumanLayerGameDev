---
description: Quick map of the CozySim Cheat Hub — the editor window, the runtime hooks each section calls, and where to add a new cheat. Use before editing/adding cheats; read the actual files for current behaviour.
---

# Cheat Hub Reference

The Cheat Hub is a single-file IMGUI `EditorWindow` opened from Unity's menu (`CozySim → Cheat Hub`). Each section is a thin UI shell that routes through a runtime hook in another file (a `CheatX()` method on a singleton, or a static helper). Most actions require Play mode; **Clear Save** and **Set Start Day** also work in edit mode.

> Read the actual files before editing — this map can drift faster than the code. If you find the code significantly different than this file update this file.

---

## The window itself

`Assets/Editor/CozySimCheatHub.cs` — the entire UI, plus two shared helpers:
- `EndActiveTutorialIfAny()` — used by *End Day Now* and *Auto-Complete Order* so a stranded tutorial overlay doesn't survive a cheat.
- `DeliverActiveMinigameIfAny()` — same idea for an active minigame; routes through `MinigameManager.Deactivate()` and returns whether it fired (so the order-complete cheat doesn't double-count).

---

## Sections → runtime hooks

| Section | Editor entry point (in `CozySimCheatHub.cs`) | Runtime hook(s) |
|---|---|---|
| Save Data | `DrawSaveSection` | `Persistence.ClearAll` (`Assets/_Scripts/Gameplay/Persistence.cs`) |
| Day → Set / End | `DrawDaySection`, `SetStartDay` | Play: `Scheduler.CheatSetDay`, `Scheduler.CheatEndDay` (`Assets/_Scripts/Scheduler/Scheduler.cs`). Edit: writes the Scheduler component's `_currentDayNumber` via `SerializedObject` (prefab preferred over scene instance). |
| Orders → Auto-Complete | `DrawOrdersSection` | `Scheduler.CheatCompleteCurrentOrder` |
| Minigame Override (force lint/wrinkle/stickers/stain) | `DrawMinigameOverrideSection`, `SaveMinigameOverridesToSession`, `LoadMinigameOverridesFromSession`, `[InitializeOnLoadMethod] BootstrapMinigameOverridesFromSession` | Writes `MinigameCheatOverrides` (`Assets/_Scripts/Gameplay/Minigame/MinigameCheatOverrides.cs`) static flags+values; consumed by `MinigameManager.Activate` (cheat > order's `overrideX` > random fallback). Persistence: `SessionState` (survives domain reload + Play mode entry). |
| Money → +$X | `DrawMoneySection` | `HUDManager.AddCheatCents` (`Assets/_Scripts/UI/HUD/HUDManager.cs`); reads `HUDManager.TotalCents` for the label. |
| Items (lock/unlock) | `DrawItemsSection`, `DrawItemRow`, `RefreshShopItems` | `Unlocker.IsOwnedPersisted` / `MarkOwned` / `MarkUnowned` (`Assets/_Scripts/Gameplay/Unlocker.cs`). Lists every `ShopItemSO` via `AssetDatabase.FindAssets`. |
| Tutorials (lock/unlock) | `DrawTutorialsSection`, `DrawTutorialRow`, `RefreshTutorials` | Reads/writes `FBPP` directly using `TutorialID.GetTutorialKey()` (mirrors what `TutorialManager.MarkTutorialCompleted` / `Persistence.ClearAll` do internally — works in edit mode without needing the singleton). `TutorialManager` is only used for the *dismiss-active-tutorial* helper above. |
| Cinematics (replay / status) | `DrawCinematicsSection`, `DrawCinematicRow`, `PlayCinematic`, `RefreshCinematics` | `CinematicRegistry.HasSeen` for status (`Assets/_Scripts/Cinematic/CinematicRegistry.cs`). Replay sets `CinematicScenePayload.Pending / ReturnSceneName / MarkSeenOnFinish=false` and calls `SceneLoader.LoadScene(CinematicScenePayload.SceneName)` so the seen flag isn't flipped. |
| Scene → Select First Clothing | `DrawSceneSection`, `SelectFirstClothingItem`, `TryExpandHierarchyNode` | Editor-only. Finds `MinigameRoot/Clothes` in the active scene and expands it via reflection on `UnityEditor.SceneHierarchyWindow`. |
| Bootstrap (header) | `OnGUI` (top of method) | `SaveManager.EnsureFBPPInitialized` (`Assets/_Scripts/Core/SaveManager.cs`) — idempotent; lets edit-mode cheats touch FBPP before play-mode `SaveManager.Bootstrap` has run. |

---

## Adding a new cheat

The pattern is the same across every section:

1. **Add the runtime hook.** A `public void CheatX(...)` method on the relevant singleton (`Scheduler`, `HUDManager`, `MinigameManager`, etc.) or a static helper on the system you're cheating against. Keep behaviour identical to the natural path so the cheat and real flow stay consistent.
2. **Add a section in `CozySimCheatHub.cs`.** Follow an existing section as the template:
   - Asset list section (Items / Tutorials / Cinematics): add `_xxxScroll`, `_xxxSearch`, `List<TSO> _xxx`, `RefreshXxx()`, `DrawXxxSection`, `DrawXxxRow`. Refresh on `OnEnable` and `OnFocus`. Use `AssetDatabase.FindAssets($"t:{nameof(TSO)}")` and color the row green/red by current state.
   - Single-button section (Save / Money / Orders): just a `DrawXxxSection` with an `EditorGUI.DisabledScope(!inPlay || !TSingleton.HasInstance)` wrapper.
3. **Wire the section into `OnGUI`** between the existing `EditorGUILayout.Space(6)` separators.
4. **If the cheat ends a phase** (day, order, etc.), call `EndActiveTutorialIfAny()` and/or `DeliverActiveMinigameIfAny()` first to avoid stranded overlays.
5. **If the cheat must work in edit mode**, route through FBPP (or `SerializedObject` on a prefab) directly rather than a singleton — see `SetStartDay` and the Tutorials section as references.
