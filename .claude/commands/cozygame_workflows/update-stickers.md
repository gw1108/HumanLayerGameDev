---
description: Reference for updating the laundering minigame sticker system. Lists every file involved and the purpose stickers serve. Use before adding variants, changing rewards, retuning spawn counts, or touching peel logic.
---

# Update Stickers Workflow

**When to use:** Adding sticker art, retuning how many spawn or what they pay out, swapping where the player can scrape them, changing the scraper tool's feel (radius, pulse, VFX), or extending the system with new behaviour.

---

## Purpose of Stickers

Stickers exist as a **small optional minigame inside the laundering loop**. While a cloth is on the **detailing table**, the player picks up the **Sticker Scraper** tool and drags it across the garment to peel stickers off — each peel awards a small cents reward and plays a slingshot VFX. They are tactile, low-stakes detail work: clearing them is encouraged but not required by `OrderEvaluator`, and unscraped stickers do not penalize the order.

Two visual styles exist, both drawn into the **same cloth shader** (no per-sticker GameObjects):

- **RandomImage** — a sprite from a curated pool (cute icons, animals, etc.).
- **HelloIAm** — a "Hello, I am ___" name badge. Each background+name combo is a single pre-rendered sprite, **not** runtime-composed text.

Both styles share the same atlas, the same placement code, and the same scraping behaviour. Adding more styles or images is mostly an art+addressables task, not a code task.

---

## Mental Model (read this first)

Stickers are **not** GameObjects. They are entries in a per-cloth UV-position array fed to the cloth's shader via a MaterialPropertyBlock — exactly like lint dots.

- At spawn, `ClothCondition.PlaceSticker(variantIdx)` picks an interior UV and records `(u, v, atlasIndex, rotation)` in a fixed-size array. The shader samples the global atlas at that rect and draws it on the cloth.
- At peel time, the **Sticker Scraper** tool (a `PulseTool`, same family as the lint roller) calls `ClothCondition.EraseStickerAt(uv, radius)` while held over the cloth. A hit removes the entry from the array, the shader stops drawing it, and the HUD gets a reward.

Knowing this is enough to navigate the rest of the system — most "where do I add X?" questions resolve to a single file once you know whether X is data, art, shader, tool feel, or reward bookkeeping.

---

## Folders and Files Worth Knowing

### Sticker code

`Assets/_Scripts/Gameplay/`
- **`ClothCondition.cs`** — owns the per-cloth state and the public sticker API: `PlaceSticker`, `EraseStickerAt`, `ActiveStickerCount`, `StickerCount`, `MaxStickerCount`, plus `WorldToSpriteUV` / `SpriteUVToWorld`. The single source of truth for "where stickers live on a cloth." Also where lint, stains, wrinkle, wetness, and fade live — sticker plumbing is a parallel of the lint plumbing right next to it.
- **`StickerLibrary.cs`** — boots the two Addressables labels (`stickers-random`, `stickers-helloiam`), packs them at runtime into a single atlas, and exposes the variant-index pools (`RandomVariantIndices`, `HelloIAmVariantIndices`) plus the global `_StickerTex` / `_StickerRects` shader bindings. Gracefully degrades to empty pools if a label fails to load.
- **`StickerNames.cs`** — the curated name pool used to author the HelloIAm sprite filenames. Today it is informational only (the names are baked into the PNG art); editing it does not change the live game on its own.
- **`PeeledSticker.cs`** — small struct returned by `EraseStickerAt`. Carries the UV/atlas-index/rotation of what was peeled so the scraper can spawn its VFX at the right spot.

`Assets/_Scripts/Gameplay/Tools/`
- **`StickerScraper.cs`** — the player-facing tool. Subclasses `PulseTool` (drag-and-hold cadence with consumable, pulse rotation, and pulse VFX). Listens to the detailing-table zone for placed/removed cloth, only acts on cloth with active stickers, and spawns the slingshot peel VFX on each successful erase. Per-peel reward const lives here.
- **`PulseTool.cs`** — base class shared with the Iron, Lint Roller, etc. Handles pulse cadence and consumable throttling; rarely needs editing for sticker work.

`Assets/_Scripts/Gameplay/Minigame/`
- **`MinigameManager.cs`** — calls `condition.StickerCount = …` and `SpawnStickers(condition)` for each cloth during `Activate`. Owns the random spawn-count helper and the coin-flip between RandomImage and HelloIAm pools. The cheat-hub override for forcing a sticker count is honoured here.
- **`MinigameSettings.cs`** — per-order authoring data. `ClothingItem.overrideStickers` (`-1` = random, `0..MaxStickerCount` = forced) is how you pin a specific count for a designed order.
- **`MinigameCheatOverrides.cs`** — `ForceStickers` / `StickerCount` toggles surfaced in the Cheat Hub.

`Assets/_Scripts/Core/`
- **`Bootstrapper.cs`** — kicks off `StickerLibrary.EnsureLoaded(...)` on boot so the atlas is built before any minigame starts.

### Reward / UI bookkeeping

`Assets/_Scripts/UI/HUD/HUDManager.cs`
- Day-scoped buckets `_dayStickerPeelCount` / `_dayStickerCents`, public getters, `AddStickerPeel(int cents)` (called by the scraper), and zeroing inside `ClearDayRevenue()`.

`Assets/_Scripts/UI/Popups/Results/ResultsPopup.cs`
- Renders a single coalesced **"Sticker Peels (xN)"** row in the day's results when at least one peel happened.

### Shader

`Assets/Shaders/DirtyClothes.shader`
- The fragment shader samples the global `_StickerTex` atlas at per-cloth `_StickerPositions[i]` rects (`_StickerRects` is keyed by atlas index). `STICKER_VARIANT_MAX` here must match the cap in `StickerLibrary` (currently `64`); `_StickerDotSize` here must match `ClothCondition._stickerDotSize`.

### Art and Addressables

`Assets/Textures/Stickers/`
- **`RandomStickers/`** — every PNG in this folder is fair game for the random pool (today: `ColorfulCute_*`, `FeministCute_*`, `GoodJob_*`).
- **`HelloIAm/`** — the name-badge sprites. Each file is a baked combination of one background (white or blue) with one name overlaid. To "add a name" you really add a pair of PNGs.

`Assets/AddressableAssetsData/`
- The **`Stickers`** group. Two labels matter: `stickers-random` (the random pool) and `stickers-helloiam` (the name-badge pool). Anything labelled here is loaded at boot into the runtime atlas; anything unlabelled is invisible to the game.

### Tool prefab and art

`Assets/Prefabs/Minigame/Tools/StickerScraper.prefab`
- The scraper tool prefab. Wires the `StickerScraper` component, its consumable, the detailing-table zone reference, the pulse VFX, and the peel VFX.

`Assets/Textures/Tools/StickerScraper.png` and `Assets/Textures/Cursor/StickerScraper_Cursor.png` (+ clicked variant)
- Tool sprite and cursor art.

---

## Common Update Touchpoints (where to look first)

| You want to… | Look at |
|---|---|
| Change the per-peel reward | `StickerScraper.cs` (`RewardCents` const) |
| Retune random spawn count range | `MinigameManager.cs` (`GetRandomStickerAmount`) |
| Change max stickers per cloth | `ClothCondition.cs` (`MaxStickerCount`) — also re-check `MinigameSettings.overrideStickers` tooltip |
| Pin a specific count for a designed order | `MinigameSettings.ClothingItem.overrideStickers` in the inspector |
| Tweak scraper feel (radius, pulse cadence, VFX) | `StickerScraper.prefab` + `StickerScraper.cs` + `PulseTool.cs` |
| Change which zone allows scraping | `StickerScraper.cs` (the `detailingTableZone` field + its `OnItemPlaced` / `OnItemRemoved` hookup) |
| Add a RandomImage sprite | Drop into `Assets/Textures/Stickers/RandomStickers/`, label it `stickers-random` in Addressables |
| Add a HelloIAm name | Author both white and blue name-badge PNGs into `Assets/Textures/Stickers/HelloIAm/`, label them `stickers-helloiam`. (Editing `StickerNames.cs` alone does nothing — names live in art.) |
| Change how stickers render on the cloth | `Assets/Shaders/DirtyClothes.shader` (and watch the `STICKER_VARIANT_MAX` / dot size constants stay in sync with code) |
| Change the day-end results row | `ResultsPopup.cs` (`Sticker Peels` row formatting) |
| Force a sticker count from the Cheat Hub | `MinigameCheatOverrides.cs` (already wired through `MinigameManager.Activate`) |

---

## What Stickers Do NOT Do

- They do **not** feed `OrderEvaluator` or affect order satisfaction.
- They do **not** persist across runs.
- They are **not** localised — name badges are baked PNGs.
- They are **not** click-to-peel; the scraper tool is the only way to remove them.
- HelloIAm has **no** runtime text composition (no `TextMeshPro`); each name+colour combo is one sprite.
