from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Sequence, TYPE_CHECKING

from utils.rods import Rod

if TYPE_CHECKING:
    from utils.pesca import FishProfile


UPGRADEABLE_STATS: Dict[str, Dict[str, object]] = {
    "luck": {"label": "Sorte", "higher_is_better": True},
    "kg_max": {"label": "Peso Max", "higher_is_better": True},
    "control": {"label": "Controle", "higher_is_better": True},
}

MAX_UPGRADE_PERCENT = 0.25
MIN_UPGRADE_PERCENT = 0.01
MIN_UPGRADE_COST = 400.0
COST_FRACTION = 0.25

RARITY_WEIGHT: Dict[str, float] = {
    "Comum": 1.0,
    "Incomum": 2.0,
    "Raro": 4.0,
    "Epico": 7.0,
    "Lendario": 12.0,
    "Mitico": 18.0,
}

_BASE_REQUIREMENT_COUNTS: Dict[str, tuple[int, int]] = {
    "Comum": (4, 8),
    "Incomum": (3, 6),
    "Raro": (2, 4),
    "Epico": (1, 3),
    "Lendario": (1, 2),
    "Mitico": (1, 1),
}


@dataclass(frozen=True)
class UpgradeRequirement:
    fish_name: str
    rarity: str
    count: int


@dataclass(frozen=True)
class UpgradeRecipe:
    rod_name: str
    fish_requirements: List[UpgradeRequirement]


@dataclass
class RodUpgradeState:
    upgrades: Dict[str, Dict[str, float]] = field(default_factory=dict)
    recipes: Dict[str, UpgradeRecipe] = field(default_factory=dict)

    def get_bonus(self, rod_name: str, stat: str) -> float:
        return self.upgrades.get(rod_name, {}).get(stat, 0.0)

    def has_upgrade(self, rod_name: str, stat: str) -> bool:
        return self.get_bonus(rod_name, stat) > 0.0

    def get_recipe(self, rod_name: str) -> UpgradeRecipe | None:
        return self.recipes.get(rod_name)

    def set_recipe(
        self,
        rod_name: str,
        requirements: Sequence[UpgradeRequirement],
    ) -> UpgradeRecipe | None:
        normalized_requirements = _normalize_requirements(requirements)
        if not rod_name or not normalized_requirements:
            return None
        recipe = UpgradeRecipe(
            rod_name=rod_name,
            fish_requirements=normalized_requirements,
        )
        self.recipes[rod_name] = recipe
        return recipe

    def clear_recipe(self, rod_name: str) -> None:
        self.recipes.pop(rod_name, None)

    def apply_upgrade(self, rod_name: str, stat: str, bonus: float) -> None:
        if stat not in UPGRADEABLE_STATS:
            return
        try:
            parsed_bonus = float(bonus)
        except (TypeError, ValueError):
            return
        if parsed_bonus <= 0:
            return
        clamped_bonus = min(MAX_UPGRADE_PERCENT, max(MIN_UPGRADE_PERCENT, parsed_bonus))
        self.upgrades.setdefault(rod_name, {})[stat] = clamped_bonus

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            rod_name: dict(stats)
            for rod_name, stats in self.upgrades.items()
            if stats
        }

    def recipes_to_dict(self) -> Dict[str, List[Dict[str, object]]]:
        serialized: Dict[str, List[Dict[str, object]]] = {}
        for rod_name, recipe in self.recipes.items():
            if not rod_name:
                continue
            serialized_requirements = [
                {
                    "fish_name": requirement.fish_name,
                    "rarity": requirement.rarity,
                    "count": requirement.count,
                }
                for requirement in recipe.fish_requirements
            ]
            if serialized_requirements:
                serialized[rod_name] = serialized_requirements
        return serialized

    def to_save_dict(self) -> Dict[str, object]:
        return {
            "bonuses": self.to_dict(),
            "recipes": self.recipes_to_dict(),
        }


def _normalize_requirements(
    raw_requirements: Sequence[UpgradeRequirement],
) -> List[UpgradeRequirement]:
    normalized: List[UpgradeRequirement] = []
    for requirement in raw_requirements:
        if not isinstance(requirement, UpgradeRequirement):
            continue
        fish_name = requirement.fish_name.strip()
        rarity = requirement.rarity.strip() or "Comum"
        try:
            count = int(requirement.count)
        except (TypeError, ValueError):
            continue
        if not fish_name or count <= 0:
            continue
        normalized.append(
            UpgradeRequirement(
                fish_name=fish_name,
                rarity=rarity,
                count=count,
            )
        )
    return normalized


def _restore_upgrade_bonuses(raw: object) -> Dict[str, Dict[str, float]]:
    restored: Dict[str, Dict[str, float]] = {}
    if not isinstance(raw, dict):
        return restored

    for rod_name, stats in raw.items():
        if not isinstance(rod_name, str) or not rod_name or not isinstance(stats, dict):
            continue
        clean_stats: Dict[str, float] = {}
        for stat, value in stats.items():
            if stat not in UPGRADEABLE_STATS:
                continue
            try:
                parsed_value = float(value)
            except (TypeError, ValueError):
                continue
            if parsed_value <= 0:
                continue
            clean_stats[stat] = min(
                MAX_UPGRADE_PERCENT,
                max(MIN_UPGRADE_PERCENT, parsed_value),
            )
        if clean_stats:
            restored[rod_name] = clean_stats
    return restored


def _restore_upgrade_recipes(raw: object) -> Dict[str, UpgradeRecipe]:
    restored: Dict[str, UpgradeRecipe] = {}
    if not isinstance(raw, dict):
        return restored

    for rod_name, raw_requirements in raw.items():
        if not isinstance(rod_name, str) or not rod_name or not isinstance(raw_requirements, list):
            continue
        normalized_requirements: List[UpgradeRequirement] = []
        for item in raw_requirements:
            if not isinstance(item, dict):
                continue
            fish_name = item.get("fish_name")
            rarity = item.get("rarity", "Comum")
            count = item.get("count")
            if not isinstance(fish_name, str) or not fish_name.strip():
                continue
            if not isinstance(rarity, str):
                rarity = "Comum"
            try:
                parsed_count = int(count)
            except (TypeError, ValueError):
                continue
            if parsed_count <= 0:
                continue
            normalized_requirements.append(
                UpgradeRequirement(
                    fish_name=fish_name.strip(),
                    rarity=rarity.strip() or "Comum",
                    count=parsed_count,
                )
            )
        if normalized_requirements:
            restored[rod_name] = UpgradeRecipe(
                rod_name=rod_name,
                fish_requirements=normalized_requirements,
            )
    return restored


def restore_rod_upgrade_state(raw: object) -> RodUpgradeState:
    state = RodUpgradeState()
    if not isinstance(raw, dict):
        return state

    raw_bonuses = raw
    raw_recipes: object = {}
    if "bonuses" in raw or "recipes" in raw:
        raw_bonuses = raw.get("bonuses")
        raw_recipes = raw.get("recipes")

    state.upgrades.update(_restore_upgrade_bonuses(raw_bonuses))
    state.recipes.update(_restore_upgrade_recipes(raw_recipes))
    return state


def compute_upgrade_cost(rod: Rod) -> float:
    return round(max(MIN_UPGRADE_COST, rod.price * COST_FRACTION), 2)


def generate_fish_requirements(
    pool_fish: Sequence["FishProfile"],
    rod: Rod,
) -> List[UpgradeRequirement]:
    del rod
    available_fish = [fish for fish in pool_fish if getattr(fish, "name", "")]
    if not available_fish:
        return []

    required_entries = min(len(available_fish), random.randint(1, 3))
    selected_fish = random.sample(available_fish, required_entries)
    requirements: List[UpgradeRequirement] = []
    for fish in selected_fish:
        rarity = getattr(fish, "rarity", "") or "Comum"
        low, high = _BASE_REQUIREMENT_COUNTS.get(rarity, (3, 6))
        requirements.append(
            UpgradeRequirement(
                fish_name=str(getattr(fish, "name", "")),
                rarity=rarity,
                count=random.randint(low, high),
            )
        )
    return requirements


def calculate_upgrade_bonus(requirements: List[UpgradeRequirement]) -> float:
    total_score = sum(
        requirement.count * RARITY_WEIGHT.get(requirement.rarity, 1.0)
        for requirement in requirements
    )
    normalized_score = min(1.0, total_score / 50.0)
    base_bonus = MIN_UPGRADE_PERCENT + (
        (MAX_UPGRADE_PERCENT - MIN_UPGRADE_PERCENT) * normalized_score
    )
    variance = random.uniform(-0.08, 0.04)
    final_bonus = base_bonus + variance
    return round(
        max(MIN_UPGRADE_PERCENT, min(MAX_UPGRADE_PERCENT, final_bonus)),
        2,
    )


def apply_stat_bonus(rod: Rod, stat: str, bonus_fraction: float) -> float:
    info = UPGRADEABLE_STATS.get(stat)
    if info is None:
        return float(getattr(rod, stat, 0.0))

    base_value = float(getattr(rod, stat, 0.0))
    effective_bonus = min(MAX_UPGRADE_PERCENT, max(0.0, float(bonus_fraction)))
    delta = abs(base_value) * effective_bonus
    if bool(info["higher_is_better"]):
        return base_value + delta
    return max(0.05, base_value - delta)


def get_effective_rod(rod: Rod, upgrade_state: RodUpgradeState) -> Rod:
    rod_bonuses = upgrade_state.upgrades.get(rod.name, {})
    if not rod_bonuses:
        return rod

    replacements = {
        stat: apply_stat_bonus(rod, stat, bonus)
        for stat, bonus in rod_bonuses.items()
        if stat in UPGRADEABLE_STATS and bonus > 0
    }
    if not replacements:
        return rod
    return replace(rod, **replacements)
