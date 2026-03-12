from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Mapping, Sequence, TYPE_CHECKING

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

_MAX_RARITY_SCORE = max(RARITY_WEIGHT.values())
_MAX_FISH_WEIGHT = 3000.0
_MAX_FISH_VALUE = 10_000.0
_MIN_REACTION_TIME = 0.8
_MAX_REACTION_TIME = 8.0
_UPGRADE_SCORE_TARGET = 4.0


@dataclass(frozen=True)
class UpgradeRequirement:
    fish_name: str
    rarity: str
    count: int


@dataclass(frozen=True)
class UpgradeRecipe:
    rod_name: str
    stat: str
    fish_requirements: List[UpgradeRequirement]


@dataclass
class RodUpgradeState:
    upgrades: Dict[str, Dict[str, float]] = field(default_factory=dict)
    recipes: Dict[str, Dict[str, UpgradeRecipe]] = field(default_factory=dict)

    def get_bonus(self, rod_name: str, stat: str) -> float:
        return self.upgrades.get(rod_name, {}).get(stat, 0.0)

    def has_upgrade(self, rod_name: str, stat: str) -> bool:
        return self.get_bonus(rod_name, stat) > 0.0

    def get_recipe(self, rod_name: str, stat: str | None = None) -> UpgradeRecipe | None:
        recipes_by_stat = self.recipes.get(rod_name, {})
        if stat is not None:
            normalized_stat = _normalize_recipe_stat(stat)
            return recipes_by_stat.get(normalized_stat) or recipes_by_stat.get("")
        if recipes_by_stat:
            return next(iter(recipes_by_stat.values()))
        return None

    def set_recipe(
        self,
        rod_name: str,
        requirements: Sequence[UpgradeRequirement],
        *,
        stat: str = "",
    ) -> UpgradeRecipe | None:
        normalized_requirements = _normalize_requirements(requirements)
        if not rod_name or not normalized_requirements:
            return None
        normalized_stat = _normalize_recipe_stat(stat)
        recipe = UpgradeRecipe(
            rod_name=rod_name,
            stat=normalized_stat,
            fish_requirements=normalized_requirements,
        )
        self.recipes.setdefault(rod_name, {})[normalized_stat] = recipe
        return recipe

    def clear_recipe(self, rod_name: str, stat: str | None = None) -> None:
        if stat is None:
            self.recipes.pop(rod_name, None)
            return
        recipes_by_stat = self.recipes.get(rod_name)
        if not recipes_by_stat:
            return
        normalized_stat = _normalize_recipe_stat(stat)
        recipes_by_stat.pop(normalized_stat, None)
        if normalized_stat:
            recipes_by_stat.pop("", None)
        if not recipes_by_stat:
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

    def recipes_to_dict(self) -> Dict[str, object]:
        serialized: Dict[str, object] = {}
        for rod_name, recipes_by_stat in self.recipes.items():
            if not rod_name:
                continue
            if len(recipes_by_stat) == 1:
                only_recipe = next(iter(recipes_by_stat.values()))
                if not only_recipe.stat:
                    serialized_requirements = _serialize_recipe_requirements(only_recipe)
                    if serialized_requirements:
                        serialized[rod_name] = serialized_requirements
                    continue
            serialized_by_stat: Dict[str, List[Dict[str, object]]] = {}
            for stat, recipe in recipes_by_stat.items():
                if stat not in UPGRADEABLE_STATS:
                    continue
                serialized_requirements = _serialize_recipe_requirements(recipe)
                if serialized_requirements:
                    serialized_by_stat[stat] = serialized_requirements
            if serialized_by_stat:
                serialized[rod_name] = serialized_by_stat
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


def _normalize_recipe_stat(stat: str | None) -> str:
    if stat in UPGRADEABLE_STATS:
        return str(stat)
    return ""


def _serialize_recipe_requirements(
    recipe: UpgradeRecipe,
) -> List[Dict[str, object]]:
    return [
        {
            "fish_name": requirement.fish_name,
            "rarity": requirement.rarity,
            "count": requirement.count,
        }
        for requirement in recipe.fish_requirements
    ]


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


def _restore_recipe_requirements(raw_requirements: object) -> List[UpgradeRequirement]:
    normalized_requirements: List[UpgradeRequirement] = []
    if not isinstance(raw_requirements, list):
        return normalized_requirements
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
    return normalized_requirements


def _restore_upgrade_recipes(raw: object) -> Dict[str, Dict[str, UpgradeRecipe]]:
    restored: Dict[str, Dict[str, UpgradeRecipe]] = {}
    if not isinstance(raw, dict):
        return restored

    for rod_name, raw_requirements in raw.items():
        if not isinstance(rod_name, str) or not rod_name:
            continue
        if isinstance(raw_requirements, list):
            normalized_requirements = _restore_recipe_requirements(raw_requirements)
            if normalized_requirements:
                restored[rod_name] = {
                    "": UpgradeRecipe(
                        rod_name=rod_name,
                        stat="",
                        fish_requirements=normalized_requirements,
                    )
                }
            continue
        if not isinstance(raw_requirements, dict):
            continue
        restored_by_stat: Dict[str, UpgradeRecipe] = {}
        for stat, stat_requirements in raw_requirements.items():
            normalized_stat = _normalize_recipe_stat(stat if isinstance(stat, str) else None)
            if normalized_stat not in UPGRADEABLE_STATS:
                continue
            normalized_requirements = _restore_recipe_requirements(stat_requirements)
            if not normalized_requirements:
                continue
            restored_by_stat[normalized_stat] = UpgradeRecipe(
                rod_name=rod_name,
                stat=normalized_stat,
                fish_requirements=normalized_requirements,
            )
        if restored_by_stat:
            restored[rod_name] = restored_by_stat
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


def _normalize_metric(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 1.0
    return (value - minimum) / (maximum - minimum)


def _normalized_rarity_score(rarity: str) -> float:
    return min(1.0, RARITY_WEIGHT.get(rarity, 1.0) / _MAX_RARITY_SCORE)


def _normalized_weight_score(weight: float) -> float:
    clamped_weight = max(0.0, min(float(weight), _MAX_FISH_WEIGHT))
    return math.log10(clamped_weight + 1.0) / math.log10(_MAX_FISH_WEIGHT + 1.0)


def _normalized_value_score(value: float) -> float:
    clamped_value = max(0.0, min(float(value), _MAX_FISH_VALUE))
    return math.log10(clamped_value + 1.0) / math.log10(_MAX_FISH_VALUE + 1.0)


def _normalized_control_score(reaction_time_s: float) -> float:
    clamped_reaction = max(_MIN_REACTION_TIME, min(float(reaction_time_s), _MAX_REACTION_TIME))
    challenge_value = 1.0 / clamped_reaction
    minimum = 1.0 / _MAX_REACTION_TIME
    maximum = 1.0 / _MIN_REACTION_TIME
    return _normalize_metric(challenge_value, minimum, maximum)


def _rod_stat_focus(rod: Rod, stat: str) -> float:
    if stat == "luck":
        return min(1.0, abs(float(rod.luck)) / 0.35)
    if stat == "kg_max":
        capped_kg = max(1.0, min(float(rod.kg_max), 3000.0))
        return min(1.0, math.log10(capped_kg) / math.log10(3000.0))
    if stat == "control":
        return min(1.0, max(0.0, float(rod.control)) / 1.5)
    return 0.0


def _rod_tier_focus(rod: Rod) -> float:
    capped_price = max(1.0, min(float(rod.price), 1_000_000.0))
    return min(1.0, math.log10(capped_price + 1.0) / 6.0)


def _requirement_selection_score(
    fish: "FishProfile",
    *,
    stat: str,
    rod_focus: float,
    tier_focus: float,
    rarity_bounds: tuple[float, float],
    weight_bounds: tuple[float, float],
    value_bounds: tuple[float, float],
    control_bounds: tuple[float, float],
) -> float:
    rarity = RARITY_WEIGHT.get(getattr(fish, "rarity", ""), 1.0)
    weight = max(
        float(getattr(fish, "kg_max", 0.0)),
        (float(getattr(fish, "kg_min", 0.0)) + float(getattr(fish, "kg_max", 0.0))) / 2,
    )
    value = float(getattr(fish, "base_value", 0.0))
    control_challenge = 1 / max(0.1, float(getattr(fish, "reaction_time_s", 2.5)))
    rarity_score = _normalize_metric(rarity, *rarity_bounds)
    weight_score = _normalize_metric(weight, *weight_bounds)
    value_score = _normalize_metric(value, *value_bounds)
    control_score = _normalize_metric(control_challenge, *control_bounds)

    generic_profile = (rarity_score * 0.55) + (value_score * 0.25) + (weight_score * 0.20)
    if stat == "kg_max":
        stat_profile = (weight_score * 0.70) + (rarity_score * 0.20) + (value_score * 0.10)
    elif stat == "control":
        stat_profile = (control_score * 0.70) + (rarity_score * 0.20) + (value_score * 0.10)
    elif stat == "luck":
        stat_profile = (rarity_score * 0.70) + (value_score * 0.30)
    else:
        stat_profile = generic_profile

    focus = min(0.90, 0.35 + (rod_focus * 0.40) + (tier_focus * 0.15))
    return (generic_profile * (1 - focus)) + (stat_profile * focus)


def _requirement_bonus_profile(
    requirement: UpgradeRequirement,
    *,
    stat: str,
    fish_by_name: Mapping[str, object] | None = None,
) -> float:
    rarity_score = _normalized_rarity_score(requirement.rarity)
    fish = fish_by_name.get(requirement.fish_name) if fish_by_name is not None else None
    if fish is None:
        return rarity_score

    weight = max(
        float(getattr(fish, "kg_max", 0.0)),
        (float(getattr(fish, "kg_min", 0.0)) + float(getattr(fish, "kg_max", 0.0))) / 2,
    )
    value = float(getattr(fish, "base_value", 0.0))
    reaction_time_s = float(getattr(fish, "reaction_time_s", 2.5))
    weight_score = _normalized_weight_score(weight)
    value_score = _normalized_value_score(value)
    control_score = _normalized_control_score(reaction_time_s)

    if stat == "kg_max":
        return (weight_score * 0.65) + (rarity_score * 0.20) + (value_score * 0.15)
    if stat == "control":
        return (control_score * 0.65) + (rarity_score * 0.20) + (value_score * 0.15)
    if stat == "luck":
        return (rarity_score * 0.60) + (value_score * 0.40)
    return rarity_score


def generate_fish_requirements(
    pool_fish: Sequence["FishProfile"],
    rod: Rod,
    stat: str = "",
) -> List[UpgradeRequirement]:
    available_fish = [fish for fish in pool_fish if getattr(fish, "name", "")]
    if not available_fish:
        return []

    required_entries = min(len(available_fish), random.randint(1, 3))
    normalized_stat = _normalize_recipe_stat(stat)
    rarity_values = [
        RARITY_WEIGHT.get(getattr(fish, "rarity", ""), 1.0)
        for fish in available_fish
    ]
    weight_values = [
        max(
            float(getattr(fish, "kg_max", 0.0)),
            (float(getattr(fish, "kg_min", 0.0)) + float(getattr(fish, "kg_max", 0.0))) / 2,
        )
        for fish in available_fish
    ]
    value_values = [float(getattr(fish, "base_value", 0.0)) for fish in available_fish]
    control_values = [
        1 / max(0.1, float(getattr(fish, "reaction_time_s", 2.5)))
        for fish in available_fish
    ]
    rod_focus = _rod_stat_focus(rod, normalized_stat)
    tier_focus = _rod_tier_focus(rod)
    ranked_fish = sorted(
        available_fish,
        key=lambda fish: _requirement_selection_score(
            fish,
            stat=normalized_stat,
            rod_focus=rod_focus,
            tier_focus=tier_focus,
            rarity_bounds=(min(rarity_values), max(rarity_values)),
            weight_bounds=(min(weight_values), max(weight_values)),
            value_bounds=(min(value_values), max(value_values)),
            control_bounds=(min(control_values), max(control_values)),
        ),
        reverse=True,
    )
    candidate_count = min(len(ranked_fish), max(required_entries, required_entries + 2))
    selected_fish = random.sample(ranked_fish[:candidate_count], required_entries)
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


def calculate_upgrade_bonus(
    requirements: List[UpgradeRequirement],
    *,
    stat: str = "",
    fish_by_name: Mapping[str, object] | None = None,
) -> float:
    normalized_stat = _normalize_recipe_stat(stat)
    total_score = sum(
        requirement.count
        * _requirement_bonus_profile(
            requirement,
            stat=normalized_stat,
            fish_by_name=fish_by_name,
        )
        for requirement in requirements
    )
    normalized_score = min(1.0, total_score / _UPGRADE_SCORE_TARGET)
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


def format_upgrade_stat_value(stat: str, value: float) -> str:
    if stat == "luck":
        return f"{value:.0%}"
    if stat == "control":
        return f"{value:+.2f}s"
    return f"{value:g}"


def format_upgrade_summary(rod: Rod, upgrade_state: RodUpgradeState | None) -> str:
    if upgrade_state is None:
        return "Sem melhorias"
    rod_bonuses = upgrade_state.upgrades.get(rod.name, {})
    if not rod_bonuses:
        return "Sem melhorias"
    parts = [
        f"{UPGRADEABLE_STATS[stat]['label']} +{int(bonus * 100)}%"
        for stat, bonus in rod_bonuses.items()
        if stat in UPGRADEABLE_STATS and bonus > 0
    ]
    return " | ".join(parts) if parts else "Sem melhorias"


def format_rod_stats(rod: Rod, upgrade_state: RodUpgradeState | None = None) -> str:
    effective_rod = get_effective_rod(rod, upgrade_state) if upgrade_state is not None else rod
    parts: List[str] = []
    for stat, label in (
        ("luck", "Sorte"),
        ("kg_max", "KGMax"),
        ("control", "Controle"),
    ):
        base_value = float(getattr(rod, stat, 0.0))
        effective_value = float(getattr(effective_rod, stat, base_value))
        if abs(effective_value - base_value) > 1e-9:
            parts.append(
                f"{label}: {format_upgrade_stat_value(stat, base_value)}"
                f" -> {format_upgrade_stat_value(stat, effective_value)}"
            )
        else:
            parts.append(f"{label}: {format_upgrade_stat_value(stat, base_value)}")
    summary = format_upgrade_summary(rod, upgrade_state)
    if summary != "Sem melhorias":
        parts.append(f"Melhorias: {summary}")
    return " | ".join(parts)


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
