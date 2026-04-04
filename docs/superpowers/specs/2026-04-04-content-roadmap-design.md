# Content Roadmap Design — Updates 1.8, 1.9, 2.0

**Date:** 2026-04-04  
**Scope:** Content brainstorm and roadmap for the next three updates. No code architecture changes except where noted.

---

## Context

Fisching is at v1.7. Content is fully data-driven JSON. The game has 27+ pools, 35+ rods, 35+ mutations, 8 hunts, 5 events, 5 weather types, and 19+ missions. This roadmap focuses on new content (pools, fish, rods, mutations, hunts, missions) organized into three versioned updates with themes.

---

## Update 1.8 — Grandes Áreas

**Theme:** The frozen north gets depth. Snowcap becomes a proper area with a hidden layer, and the pool selection UI gains a Major Areas grouping.

### Major Areas (UI)
- Pools are reorganized under named "major areas"
- Selecting a major area prompts the player to choose a sub-pool
- No gameplay change — purely organizational
- Grouping details to be decided during implementation

### New Content
- **New sub-pool: `Gruta Glacial`**
  - A cave system under the Snowcap ice sheet
  - ~10 fish: deep cold-water species, bioluminescent under-ice life, rare arctic predator
  - Unlock condition: Snowcap bestiary % + deliver a specific rare fish via mission chain

- **New hunt:** Colossal ice creature beneath the glacier — Snowcap area boss
  - Drops unique reward (material for craftable rod or exclusive item)

- **New rods: 1–2**
  - One buyable in Snowcap
  - One craftable or hunt-locked
  - Snowcap/ice theme

- **New mutations: 2**
  - 1 universal frost-themed (low %, XP/gold bonus)
  - 1 rod-exclusive (tied to one of the new Snowcap rods)

---

## Update 1.9 — Colinas Terrapin

**Theme:** A lush hilly turtle island — warm and tropical, contrasting 1.8's ice. Inspired by Terrapin Island from Fisch.

### New Major Area: `Colinas Terrapin`

- **Sub-pool 1: `Baía Escamosa`**
  - Warm coastal bay at the base of the hills, entry point
  - Mid-game accessibility
  - ~10 fish: tropical reef fish, sea turtles of various sizes/rarities

- **Sub-pool 2: `Lago do Cume`**
  - Serene mist-covered mountain lake at the island's summit
  - Unlocked via second mission chain after discovering the island
  - ~10 fish: rare high-altitude freshwater species, ancient giant turtle elders

### New Content
- **New hunt:** Colossal ancient sea turtle — mythic-tier boss at the summit lake
  - Drops crafting materials for the craftable rod

- **New rods: 1–2**
  - One buyable on the island (Baía Escamosa)
  - One craftable with hunt drops
  - Nature/coral/island theme

- **New mutations: 1**
  - 1 universal nature/ocean themed (low %, XP/gold bonus)

- **New questline:**
  - Part 1: discover and unlock Colinas Terrapin → access Baía Escamosa
  - Part 2: climb to the summit → unlock Lago do Cume

---

## Update 2.0 — Queda da Maré (Milestone)

**Theme:** A place isolated by the ocean itself. Waterfalls pour endlessly from the edges into an abyss below. The streams carve paths into five distinct equal zones. No hierarchy — each zone is its own identity, reached by its own stream.

### New Major Area: `Queda da Maré`

**5 pools (names TBD), equal in progression weight, themed as:**
- Coral zone
- Relics/ruins zone
- Kings/noble creatures zone
- Mist/ethereal zone
- Abyss-edge zone

Each pool:
- ~10 fish unique to that zone
- 1 exclusive hunt (normal variant)
- 1 exclusive hunt (rarer variant of same boss)
- Total: 10 hunts across the area

### New Content
- **New rods: 3**
  - Each craftable using drops from one of the 5 hunt bosses (3 of 5 hunts yield rod materials)
  - Themed to their respective zone

- **New questline:**
  - Multi-part chain to find and enter Queda da Maré
  - Per-zone chains to unlock each of the 5 pools

---

## Loose Ideas (Not Scheduled)

- **Area/pool-specific events:** events scoped to a region or pool (e.g. blizzard only in Snowcap). Requires new region-scoped event logic. Worth a design pass before next event.
- **Rachadura Vulcânica expansion:** new sub-pool deeper in the rift, magma/armor fish, fire boss. Shelved.
- **Ancient ruins area:** archaeological theme (inspired by Ancient Isle / Statue of Sovereignty / Keepers Altar in Fisch). Not yet scheduled.
- **Forsaken Shore:** abandoned coastline, storm-weathered fish, wrecks. Not yet scheduled.
