# Rod Upgrade Stat-Scaling Design

## Problem

The current rod upgrade system almost always requires mythic fish regardless of rod strength. A starter rod and an endgame rod face the same rarity demands. Additionally, turning in rare fish always gives proportionally the same bonus, making upgrades feel flat across the progression curve.

## Design: Stat-Strength Multiplier (Approach A)

A single `stat_strength` factor (0.0–1.0) drives two changes:

1. **Requirement rarity scales with stat strength** — weak rods mostly need common fish, strong rods need rare fish.
2. **Bonus from rare fish diminishes with stat strength** — weak rods get near-max bonus from rare fish, strong rods get reduced bonus.

### stat_strength computation

`_stat_strength(rod, stat, all_rods)` normalizes the rod's stat value against the min/max of that stat across all loaded rods.

- `luck` and `control`: linear normalization `(value - min) / (max - min)`
- `kg_max`: log-scale normalization `(log10(value) - log10(min)) / (log10(max) - log10(min))` since the range is exponential (2.5–3000+)
- Result clamped to 0.0–1.0

Ranges are derived dynamically from loaded rods, so adding new rods with extreme stats shifts the scale automatically.

**Edge cases:**
- **Single rod or all identical stats** (`max == min`): return `0.5` (neutral midpoint — neither strong nor weak behavior).
- **`kg_max <= 0`**: clamp to `max(1.0, value)` before log10.
- The `stat` parameter is always the stat being upgraded.

### Requirement selection: rarity dampening

In `_requirement_selection_score`, the rarity score component is modulated:

```
effective_rarity_score = rarity_score * (RARITY_SELECTION_FLOOR + (1 - RARITY_SELECTION_FLOOR) * stat_strength)
```

- `_RARITY_SELECTION_FLOOR = 0.2` — minimum rarity influence
- Weak rod (stat_strength ~0.1): rarity counts ~28% of current → common fish rank competitively
- Strong rod (stat_strength ~0.9): rarity counts ~92% → near-current behavior

Other scoring components (weight, value, control challenge) are unchanged. Stat-specific focus (kg_max upgrades favor heavy fish, etc.) is preserved.

**Interaction with existing `_rod_stat_focus` / `_rod_tier_focus`:** These existing mechanisms bias which *type* of fish is preferred (heavy fish for kg_max, etc.) and scale with rod price. They remain unchanged. `stat_strength` only modulates *rarity's weight* in the score — a different axis. The two systems are complementary, not redundant.

### Bonus calculation: diminishing returns

In `_requirement_bonus_profile`, the rarity contribution to bonus is dampened:

```
effective_rarity = rarity_score * (1.0 - RARITY_BONUS_DAMPING * stat_strength)
```

- `_RARITY_BONUS_DAMPING = 0.7` — max penalty on rarity bonus for strong rods
- Weak rod (stat_strength ~0.1): mythic gives ~93% of full rarity bonus → near-max upgrade
- Strong rod (stat_strength ~0.9): mythic gives ~37% of rarity bonus → mediocre upgrade

### Expected feel

| Rod | Stat strength | Likely requirements | Mythic bonus |
|-----|--------------|-------------------|-------------|
| Vara Bambu (luck 0.05) | ~0.06 | Mostly Comum/Incomum | Near-max (~23-25%) |
| Vara Tundra (luck 0.25) | ~0.35 | Mixed, some Raro | Good (~16-20%) |
| Azul Lamina (luck 0.70) | ~1.0 | Often Mitico/Lendario | Weak (~5-10%) |

Assumed luck range: 0.01 (Maos) – 0.70 (Azul Lamina). Linear normalization: `(value - 0.01) / (0.70 - 0.01)`.

### API changes

Functions that gain new parameters:

- `generate_fish_requirements(pool_fish, rod, stat, all_rods)` — needs `all_rods: Sequence[Rod]` to compute stat_strength
- `calculate_upgrade_bonus(requirements, stat, fish_by_name, rod, all_rods)` — same reason

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `_RARITY_SELECTION_FLOOR` | 0.2 | Minimum rarity influence in fish selection |
| `_RARITY_BONUS_DAMPING` | 0.7 | Max rarity bonus penalty for strong rods |

### Callers to update

- `utils/pesca.py` — wherever `generate_fish_requirements` and `calculate_upgrade_bonus` are called, pass `all_rods`
- `utils/market.py` — if it calls either function, same treatment
- `tests/test_rod_upgrades_characterization.py` — update test calls with `all_rods` parameter

### Save compatibility

No save format changes. `RodUpgradeState` serialization is unaffected — only the generation and calculation logic changes.
