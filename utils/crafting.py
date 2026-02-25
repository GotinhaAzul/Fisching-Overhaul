from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, TYPE_CHECKING

from utils.inventory import InventoryEntry
from utils.requirements_common import (
    collect_countable_fish_names,
    completion_percent,
    count_fish_mutation_pair,
    count_name_case_insensitive,
    fish_counts_for_bestiary_completion,
    fish_mutation_key,
    fish_name_matches,
    pool_counts_for_bestiary_completion,
    safe_float,
    safe_int,
    safe_str,
    seconds_from_requirement,
)

if TYPE_CHECKING:
    from utils.rods import Rod


ANY_KEY = "__any__"


@dataclass
class CraftingDefinition:
    craft_id: str
    rod_name: str
    name: str
    description: str
    unlock_mode: str
    unlock_requirements: List[Dict[str, object]]
    craft_requirements: List[Dict[str, object]]
    starts_visible: bool = False


@dataclass
class CraftingState:
    unlocked: Set[str] = field(default_factory=set)
    crafted: Set[str] = field(default_factory=set)
    announced: Set[str] = field(default_factory=set)


@dataclass
class CraftingProgress:
    find_fish_counts_by_name: Dict[str, int] = field(default_factory=dict)
    find_mutation_counts_by_name: Dict[str, int] = field(default_factory=dict)
    find_fish_with_mutation_pair_counts: Dict[str, int] = field(default_factory=dict)
    delivered_fish_counts_by_craft: Dict[str, Dict[str, int]] = field(default_factory=dict)
    delivered_mutation_counts_by_craft: Dict[str, Dict[str, int]] = field(default_factory=dict)
    delivered_fish_with_mutation_pair_counts_by_craft: Dict[str, Dict[str, int]] = field(
        default_factory=dict
    )
    paid_money_by_craft: Dict[str, float] = field(default_factory=dict)

    def record_find(self, fish_name: str, mutation_name: Optional[str]) -> None:
        self.find_fish_counts_by_name[fish_name] = self.find_fish_counts_by_name.get(fish_name, 0) + 1
        if not mutation_name:
            return

        self.find_mutation_counts_by_name[mutation_name] = (
            self.find_mutation_counts_by_name.get(mutation_name, 0) + 1
        )
        pair_key = _fish_mutation_key(fish_name, mutation_name)
        self.find_fish_with_mutation_pair_counts[pair_key] = (
            self.find_fish_with_mutation_pair_counts.get(pair_key, 0) + 1
        )


def load_crafting_definitions(
    base_dir: Path,
    *,
    valid_rod_names: Optional[Set[str]] = None,
) -> List[CraftingDefinition]:
    if not base_dir.exists():
        return []

    definitions: List[CraftingDefinition] = []
    for craft_dir in sorted(path for path in base_dir.iterdir() if path.is_dir()):
        config_path = craft_dir / f"{craft_dir.name}.json"
        if not config_path.exists():
            json_candidates = sorted(craft_dir.glob("*.json"))
            if len(json_candidates) != 1:
                continue
            config_path = json_candidates[0]

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            print(f"[crafting] Ignorando arquivo invalido: {config_path}")
            continue
        if not isinstance(data, dict):
            print(f"[crafting] Ignorando receita malformada: {config_path}")
            continue

        craft_id = data.get("id", craft_dir.name)
        rod_name = data.get("rod_name")
        if not isinstance(craft_id, str) or not craft_id:
            print(f"[crafting] Receita sem id valido: {config_path}")
            continue
        if not isinstance(rod_name, str) or not rod_name:
            print(f"[crafting] Receita sem rod_name valido: {config_path}")
            continue
        if valid_rod_names is not None and rod_name not in valid_rod_names:
            print(f"[crafting] Vara inexistente em receita {craft_id}: {rod_name}")
            continue

        unlock_data = data.get("unlock")
        unlock_mode = "all"
        unlock_requirements: List[Dict[str, object]] = []
        if isinstance(unlock_data, dict):
            raw_mode = unlock_data.get("mode", "all")
            if isinstance(raw_mode, str) and raw_mode.lower() in {"all", "any"}:
                unlock_mode = raw_mode.lower()
            unlock_requirements = _extract_requirement_list(unlock_data.get("requirements"))

        craft_data = data.get("craft")
        craft_requirements = _extract_requirement_list(
            craft_data.get("requirements") if isinstance(craft_data, dict) else []
        )

        definitions.append(
            CraftingDefinition(
                craft_id=craft_id,
                rod_name=rod_name,
                name=_safe_str(data.get("name"), fallback=craft_id),
                description=_safe_str(data.get("description")),
                unlock_mode=unlock_mode,
                unlock_requirements=unlock_requirements,
                craft_requirements=craft_requirements,
                starts_visible=bool(data.get("starts_visible", False)),
            )
        )

    return definitions


def serialize_crafting_state(state: CraftingState) -> Dict[str, object]:
    return {
        "unlocked": sorted(state.unlocked),
        "crafted": sorted(state.crafted),
        "announced": sorted(state.announced),
    }


def restore_crafting_state(
    raw_state: object,
    definitions: Sequence[CraftingDefinition],
) -> CraftingState:
    valid_ids = {definition.craft_id for definition in definitions}
    default_unlocked = {
        definition.craft_id
        for definition in definitions
        if definition.starts_visible
    }
    state = CraftingState(unlocked=set(default_unlocked))
    if not isinstance(raw_state, dict):
        return state

    for key, target in (
        ("unlocked", state.unlocked),
        ("crafted", state.crafted),
        ("announced", state.announced),
    ):
        raw_list = raw_state.get(key)
        if not isinstance(raw_list, list):
            continue
        for craft_id in raw_list:
            if isinstance(craft_id, str) and craft_id in valid_ids:
                target.add(craft_id)

    return state


def serialize_crafting_progress(progress: CraftingProgress) -> Dict[str, object]:
    return {
        "find_fish_counts_by_name": progress.find_fish_counts_by_name,
        "find_mutation_counts_by_name": progress.find_mutation_counts_by_name,
        "find_fish_with_mutation_pair_counts": progress.find_fish_with_mutation_pair_counts,
        "delivered_fish_counts_by_craft": progress.delivered_fish_counts_by_craft,
        "delivered_mutation_counts_by_craft": progress.delivered_mutation_counts_by_craft,
        "delivered_fish_with_mutation_pair_counts_by_craft": (
            progress.delivered_fish_with_mutation_pair_counts_by_craft
        ),
        "paid_money_by_craft": progress.paid_money_by_craft,
    }


def restore_crafting_progress(raw_progress: object) -> CraftingProgress:
    progress = CraftingProgress()
    if not isinstance(raw_progress, dict):
        return progress

    progress.find_fish_counts_by_name = _safe_str_int_map(raw_progress.get("find_fish_counts_by_name"))
    progress.find_mutation_counts_by_name = _safe_str_int_map(raw_progress.get("find_mutation_counts_by_name"))
    progress.find_fish_with_mutation_pair_counts = _safe_str_int_map(
        raw_progress.get("find_fish_with_mutation_pair_counts")
    )
    progress.delivered_fish_counts_by_craft = _safe_nested_str_int_map(
        raw_progress.get("delivered_fish_counts_by_craft")
    )
    progress.delivered_mutation_counts_by_craft = _safe_nested_str_int_map(
        raw_progress.get("delivered_mutation_counts_by_craft")
    )
    progress.delivered_fish_with_mutation_pair_counts_by_craft = _safe_nested_str_int_map(
        raw_progress.get("delivered_fish_with_mutation_pair_counts_by_craft")
    )
    progress.paid_money_by_craft = _safe_str_float_map(raw_progress.get("paid_money_by_craft"))
    return progress


def update_crafting_unlocks(
    definitions: Sequence[CraftingDefinition],
    state: CraftingState,
    progress: CraftingProgress,
    *,
    level: int,
    pools: Sequence[object],
    discovered_fish: Set[str],
    unlocked_pools: Set[str],
    mission_state: object,
    unlocked_rods: Set[str],
    play_time_seconds: float,
    inventory_fish_counts: Optional[Dict[str, int]] = None,
    inventory_mutation_counts: Optional[Dict[str, int]] = None,
) -> List[CraftingDefinition]:
    newly_unlocked: List[CraftingDefinition] = []
    for definition in definitions:
        if definition.craft_id in state.crafted:
            continue
        if not is_craft_unlocked(
            definition,
            state,
            progress,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
            unlocked_pools=unlocked_pools,
            mission_state=mission_state,
            unlocked_rods=unlocked_rods,
            play_time_seconds=play_time_seconds,
            inventory_fish_counts=inventory_fish_counts,
            inventory_mutation_counts=inventory_mutation_counts,
        ):
            continue
        if definition.craft_id not in state.unlocked:
            state.unlocked.add(definition.craft_id)
        if definition.craft_id in state.announced:
            continue
        state.announced.add(definition.craft_id)
        newly_unlocked.append(definition)

    return newly_unlocked


def is_craft_unlocked(
    definition: CraftingDefinition,
    state: CraftingState,
    progress: CraftingProgress,
    *,
    level: int,
    pools: Sequence[object],
    discovered_fish: Set[str],
    unlocked_pools: Set[str],
    mission_state: object,
    unlocked_rods: Set[str],
    play_time_seconds: float,
    inventory_fish_counts: Optional[Dict[str, int]] = None,
    inventory_mutation_counts: Optional[Dict[str, int]] = None,
) -> bool:
    if definition.craft_id in state.unlocked:
        return True
    if not definition.unlock_requirements:
        return True

    results = [
        _check_unlock_requirement(
            requirement,
            progress,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
            unlocked_pools=unlocked_pools,
            mission_state=mission_state,
            unlocked_rods=unlocked_rods,
            play_time_seconds=play_time_seconds,
            inventory_fish_counts=inventory_fish_counts,
            inventory_mutation_counts=inventory_mutation_counts,
        )
        for requirement in definition.unlock_requirements
    ]
    if definition.unlock_mode == "any":
        return any(results)
    return all(results)


def _format_craft_fish_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    del level
    target = max(0, _safe_int(requirement.get("count", 0)))
    fish_name = _safe_str(requirement.get("fish_name"))
    current = _delivered_fish_count(progress, craft_id, fish_name)
    label = f"Entregar peixe {fish_name}" if fish_name else "Entregar peixes"
    return label, current, target, current >= target


def _format_craft_mutation_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    del level
    target = max(0, _safe_int(requirement.get("count", 0)))
    mutation_name = _safe_str(requirement.get("mutation_name"))
    current = _delivered_mutation_count(progress, craft_id, mutation_name)
    label = (
        f"Entregar mutacao {mutation_name}"
        if mutation_name
        else "Entregar peixe com mutacao"
    )
    return label, current, target, current >= target


def _format_craft_fish_with_mutation_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    del level
    target = max(0, _safe_int(requirement.get("count", 0)))
    fish_name = _safe_str(requirement.get("fish_name"))
    mutation_name = _safe_str(requirement.get("mutation_name"))
    current = _delivered_fish_with_mutation_count(
        progress,
        craft_id,
        fish_name,
        mutation_name,
    )
    if fish_name and mutation_name:
        label = f"Entregar {fish_name} com mutacao {mutation_name}"
    elif fish_name:
        label = f"Entregar {fish_name} com mutacao"
    elif mutation_name:
        label = f"Entregar mutacao {mutation_name}"
    else:
        label = "Entregar peixe com mutacao"
    return label, current, target, current >= target


def _format_craft_money_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    del level
    target = max(0, int(round(_safe_float(requirement.get("amount", 0.0)))))
    current = max(
        0,
        int(round(progress.paid_money_by_craft.get(craft_id, 0.0))),
    )
    return "Pagar dinheiro", current, target, current >= target


def _format_craft_level_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    del craft_id, progress
    target = max(0, _safe_int(requirement.get("level")))
    current = max(0, int(level))
    return "Nivel", current, target, current >= target


_CRAFT_REQUIREMENT_FORMATTERS = {
    "fish": _format_craft_fish_requirement,
    "mutation": _format_craft_mutation_requirement,
    "fish_with_mutation": _format_craft_fish_with_mutation_requirement,
    "money": _format_craft_money_requirement,
    "level": _format_craft_level_requirement,
}


def format_crafting_requirement(
    requirement: Dict[str, object],
    craft_id: str,
    progress: CraftingProgress,
    level: int,
) -> Tuple[str, int, int, bool]:
    requirement_type = requirement.get("type")
    formatter = _CRAFT_REQUIREMENT_FORMATTERS.get(requirement_type)
    if formatter is None:
        return "Requisito desconhecido", 0, 1, False
    return formatter(requirement, craft_id, progress, level)


def is_craft_ready(
    definition: CraftingDefinition,
    progress: CraftingProgress,
    level: int,
) -> bool:
    for requirement in definition.craft_requirements:
        _, _, _, done = format_crafting_requirement(
            requirement,
            definition.craft_id,
            progress,
            level,
        )
        if not done:
            return False
    return True


def get_craft_deliverable_indexes(
    definition: CraftingDefinition,
    progress: CraftingProgress,
    inventory: Sequence[InventoryEntry],
) -> List[int]:
    return [
        idx
        for idx, entry in enumerate(inventory, start=1)
        if _entry_matches_any_pending_requirement(
            entry,
            definition,
            progress,
        )
    ]


def deliver_inventory_entry_for_craft(
    definition: CraftingDefinition,
    progress: CraftingProgress,
    inventory: List[InventoryEntry],
    inventory_index_1_based: int,
) -> Optional[InventoryEntry]:
    if not (1 <= inventory_index_1_based <= len(inventory)):
        return None

    entry = inventory[inventory_index_1_based - 1]
    if not _entry_matches_any_pending_requirement(entry, definition, progress):
        return None

    delivered = inventory.pop(inventory_index_1_based - 1)
    _apply_delivery_progress(definition, progress, delivered)
    return delivered


def required_money_for_craft(
    definition: CraftingDefinition,
    progress: CraftingProgress,
) -> float:
    total_required = 0.0
    for requirement in definition.craft_requirements:
        if requirement.get("type") != "money":
            continue
        total_required += max(0.0, _safe_float(requirement.get("amount", 0.0)))

    paid = max(0.0, progress.paid_money_by_craft.get(definition.craft_id, 0.0))
    return max(0.0, total_required - paid)


def pay_craft_requirement(
    definition: CraftingDefinition,
    progress: CraftingProgress,
    amount: float,
) -> float:
    if amount <= 0:
        return 0.0
    remaining = required_money_for_craft(definition, progress)
    accepted = min(amount, remaining)
    if accepted <= 0:
        return 0.0

    progress.paid_money_by_craft[definition.craft_id] = (
        progress.paid_money_by_craft.get(definition.craft_id, 0.0) + accepted
    )
    return accepted


def apply_craft_submission(
    definition: CraftingDefinition,
    state: CraftingState,
    progress: CraftingProgress,
    available_rods: Sequence["Rod"],
    owned_rods: List["Rod"],
    unlocked_rods: Set[str],
    *,
    level: int,
) -> Tuple[bool, str]:
    if definition.craft_id in state.crafted:
        return False, "Essa receita ja foi concluida."
    if not is_craft_ready(definition, progress, level):
        return False, "Os requisitos ainda nao foram concluidos."

    rods_by_name = {rod.name: rod for rod in available_rods}
    rod = rods_by_name.get(definition.rod_name)
    if not rod:
        return False, "Vara da receita nao encontrada."

    if rod.name not in {owned.name for owned in owned_rods}:
        owned_rods.append(rod)
    unlocked_rods.add(rod.name)
    state.crafted.add(definition.craft_id)
    state.unlocked.add(definition.craft_id)
    return True, f"Vara criada com sucesso: {rod.name}"


def has_any_pool_bestiary_full_completion(
    pools: Sequence[object],
    discovered_fish: Set[str],
) -> bool:
    for pool in pools:
        if not _pool_counts_for_bestiary_completion(pool):
            continue
        fish_profiles = getattr(pool, "fish_profiles", [])
        fish_names = {
            getattr(fish, "name", "")
            for fish in fish_profiles
            if getattr(fish, "name", "")
            and _fish_counts_for_bestiary_completion(fish)
        }
        if not fish_names:
            continue
        if all(fish_name in discovered_fish for fish_name in fish_names):
            return True
    return False


def _check_unlock_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    *,
    level: int,
    pools: Sequence[object],
    discovered_fish: Set[str],
    unlocked_pools: Set[str],
    mission_state: object,
    unlocked_rods: Set[str],
    play_time_seconds: float,
    inventory_fish_counts: Optional[Dict[str, int]] = None,
    inventory_mutation_counts: Optional[Dict[str, int]] = None,
) -> bool:
    context = _UnlockRequirementContext(
        level=level,
        pools=pools,
        discovered_fish=discovered_fish,
        unlocked_pools=unlocked_pools,
        mission_state=mission_state,
        unlocked_rods=unlocked_rods,
        play_time_seconds=play_time_seconds,
        inventory_fish_counts=inventory_fish_counts,
        inventory_mutation_counts=inventory_mutation_counts,
    )
    requirement_type = requirement.get("type")
    checker = _UNLOCK_REQUIREMENT_CHECKERS.get(requirement_type)
    if checker is None:
        return False
    return checker(requirement, progress, context)


@dataclass(frozen=True)
class _UnlockRequirementContext:
    level: int
    pools: Sequence[object]
    discovered_fish: Set[str]
    unlocked_pools: Set[str]
    mission_state: object
    unlocked_rods: Set[str]
    play_time_seconds: float
    inventory_fish_counts: Optional[Dict[str, int]]
    inventory_mutation_counts: Optional[Dict[str, int]]


def _check_unlock_level_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    return context.level >= max(0, _safe_int(requirement.get("level")))


def _check_unlock_bestiary_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    target = max(0.0, _safe_float(requirement.get("percent", 0.0)))
    pool_name = _safe_str(requirement.get("pool_name"))
    completion = _calculate_bestiary_completion(
        context.pools,
        context.discovered_fish,
        pool_name=pool_name if pool_name else None,
    )
    return completion >= target


def _check_unlock_find_fish_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    target = max(0, _safe_int(requirement.get("count", 0)))
    fish_name = _safe_str(requirement.get("fish_name"))
    if not fish_name:
        return False
    found_count = _count_name_case_insensitive(progress.find_fish_counts_by_name, fish_name)
    inventory_count = (
        _count_name_case_insensitive(context.inventory_fish_counts, fish_name)
        if context.inventory_fish_counts is not None
        else 0
    )
    return found_count >= target or inventory_count >= target


def _check_unlock_find_mutation_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    target = max(0, _safe_int(requirement.get("count", 0)))
    mutation_name = _safe_str(requirement.get("mutation_name"))
    if not mutation_name:
        return False
    found_count = progress.find_mutation_counts_by_name.get(mutation_name, 0)
    inventory_count = (
        max(0, _safe_int(context.inventory_mutation_counts.get(mutation_name, 0)))
        if context.inventory_mutation_counts is not None
        else 0
    )
    return found_count >= target or inventory_count >= target


def _check_unlock_pool_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    pool_name = _safe_str(requirement.get("pool_name"))
    if not pool_name:
        return False
    normalized = {item.strip().casefold() for item in context.unlocked_pools}
    return pool_name.strip().casefold() in normalized


def _check_unlock_quest_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    mission_id = _safe_str(requirement.get("mission_id"))
    state_name = _safe_str(requirement.get("state"), fallback="completed").casefold()
    if not mission_id:
        return False
    state_values = _extract_mission_state(context.mission_state)
    if state_name == "unlocked":
        return mission_id in state_values["unlocked"]
    if state_name == "claimed":
        return mission_id in state_values["claimed"]
    return mission_id in state_values["completed"]


def _check_unlock_time_played_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    target_seconds = _seconds_from_requirement(requirement)
    return context.play_time_seconds >= target_seconds


def _check_unlock_rod_requirement(
    requirement: Dict[str, object],
    progress: CraftingProgress,
    context: _UnlockRequirementContext,
) -> bool:
    del progress
    rod_name = _safe_str(requirement.get("rod_name"))
    return bool(rod_name) and rod_name in context.unlocked_rods


_UNLOCK_REQUIREMENT_CHECKERS = {
    "level": _check_unlock_level_requirement,
    "bestiary": _check_unlock_bestiary_requirement,
    "bestiary_percent": _check_unlock_bestiary_requirement,
    "find_fish": _check_unlock_find_fish_requirement,
    "find_mutation": _check_unlock_find_mutation_requirement,
    "unlock_pool": _check_unlock_pool_requirement,
    "unlock_quest": _check_unlock_quest_requirement,
    "time_played": _check_unlock_time_played_requirement,
    "unlock_rod": _check_unlock_rod_requirement,
}


def _calculate_bestiary_completion(
    pools: Sequence[object],
    discovered_fish: Set[str],
    *,
    pool_name: Optional[str] = None,
) -> float:
    if pool_name:
        normalized_pool_name = pool_name.strip().casefold()
        target_pool = next(
            (
                pool
                for pool in pools
                if _pool_matches_name(pool, normalized_pool_name)
            ),
            None,
        )
        if target_pool is None:
            return 0.0
        if not _pool_counts_for_bestiary_completion(target_pool):
            return 0.0
        fish_names = {
            getattr(fish, "name", "")
            for fish in getattr(target_pool, "fish_profiles", [])
            if getattr(fish, "name", "")
            and _fish_counts_for_bestiary_completion(fish)
        }
        return completion_percent(fish_names, discovered_fish)

    all_fish_names = collect_countable_fish_names(pools)
    return completion_percent(all_fish_names, discovered_fish)


def count_inventory_fish(inventory: Sequence[InventoryEntry]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in inventory:
        counts[entry.name] = counts.get(entry.name, 0) + 1
    return counts


def count_inventory_mutations(inventory: Sequence[InventoryEntry]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in inventory:
        mutation_name = _safe_str(entry.mutation_name)
        if not mutation_name:
            continue
        counts[mutation_name] = counts.get(mutation_name, 0) + 1
    return counts


def _pool_matches_name(pool: object, normalized_name: str) -> bool:
    pool_name = _safe_str(getattr(pool, "name", ""))
    if pool_name and pool_name.strip().casefold() == normalized_name:
        return True

    folder = getattr(pool, "folder", None)
    folder_name = _safe_str(getattr(folder, "name", ""))
    return bool(folder_name) and folder_name.strip().casefold() == normalized_name


def _pool_counts_for_bestiary_completion(pool: object) -> bool:
    return pool_counts_for_bestiary_completion(pool)


def _fish_counts_for_bestiary_completion(fish: object) -> bool:
    return fish_counts_for_bestiary_completion(fish)


def _entry_matches_any_pending_requirement(
    entry: InventoryEntry,
    definition: CraftingDefinition,
    progress: CraftingProgress,
) -> bool:
    for requirement in definition.craft_requirements:
        requirement_type = requirement.get("type")
        if requirement_type not in {"fish", "mutation", "fish_with_mutation"}:
            continue
        _, _, _, done = format_crafting_requirement(
            requirement,
            definition.craft_id,
            progress,
            level=0,
        )
        if done:
            continue

        fish_name = _safe_str(requirement.get("fish_name"))
        mutation_name = _safe_str(requirement.get("mutation_name"))
        if requirement_type == "fish":
            if not fish_name or _fish_name_matches(entry.name, fish_name):
                return True
        elif requirement_type == "mutation":
            if not entry.mutation_name:
                continue
            if not mutation_name or entry.mutation_name == mutation_name:
                return True
        elif requirement_type == "fish_with_mutation":
            if not entry.mutation_name:
                continue
            fish_ok = (not fish_name) or _fish_name_matches(entry.name, fish_name)
            mutation_ok = (not mutation_name) or (entry.mutation_name == mutation_name)
            if fish_ok and mutation_ok:
                return True
    return False


def _apply_delivery_progress(
    definition: CraftingDefinition,
    progress: CraftingProgress,
    entry: InventoryEntry,
) -> None:
    craft_id = definition.craft_id
    for requirement in definition.craft_requirements:
        requirement_type = requirement.get("type")
        fish_name = _safe_str(requirement.get("fish_name"))
        mutation_name = _safe_str(requirement.get("mutation_name"))
        _, _, _, done = format_crafting_requirement(
            requirement,
            craft_id,
            progress,
            level=0,
        )
        if done:
            continue

        if requirement_type == "fish":
            if fish_name and not _fish_name_matches(entry.name, fish_name):
                continue
            _increment_nested_counter(
                progress.delivered_fish_counts_by_craft,
                craft_id,
                fish_name or ANY_KEY,
            )
        elif requirement_type == "mutation":
            if not entry.mutation_name:
                continue
            if mutation_name and entry.mutation_name != mutation_name:
                continue
            _increment_nested_counter(
                progress.delivered_mutation_counts_by_craft,
                craft_id,
                mutation_name or ANY_KEY,
            )
        elif requirement_type == "fish_with_mutation":
            if not entry.mutation_name:
                continue
            if fish_name and not _fish_name_matches(entry.name, fish_name):
                continue
            if mutation_name and entry.mutation_name != mutation_name:
                continue
            pair_key = _fish_mutation_key(
                fish_name or ANY_KEY,
                mutation_name or ANY_KEY,
            )
            _increment_nested_counter(
                progress.delivered_fish_with_mutation_pair_counts_by_craft,
                craft_id,
                pair_key,
            )


def _extract_mission_state(mission_state: object) -> Dict[str, Set[str]]:
    if isinstance(mission_state, dict):
        return {
            "unlocked": _extract_str_set(mission_state.get("unlocked")),
            "completed": _extract_str_set(mission_state.get("completed")),
            "claimed": _extract_str_set(mission_state.get("claimed")),
        }
    return {
        "unlocked": _extract_str_set(getattr(mission_state, "unlocked", None)),
        "completed": _extract_str_set(getattr(mission_state, "completed", None)),
        "claimed": _extract_str_set(getattr(mission_state, "claimed", None)),
    }


def _extract_requirement_list(raw_value: object) -> List[Dict[str, object]]:
    if not isinstance(raw_value, list):
        return []
    return [item for item in raw_value if isinstance(item, dict)]


def _safe_int(value: object) -> int:
    return safe_int(value)


def _safe_float(value: object) -> float:
    return safe_float(value)


def _safe_str(value: object, *, fallback: str = "") -> str:
    return safe_str(value, fallback=fallback)


def _safe_str_int_map(value: object) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    parsed: Dict[str, int] = {}
    for key, raw_count in value.items():
        if isinstance(key, str):
            parsed[key] = max(0, _safe_int(raw_count))
    return parsed


def _safe_nested_str_int_map(value: object) -> Dict[str, Dict[str, int]]:
    if not isinstance(value, dict):
        return {}
    parsed: Dict[str, Dict[str, int]] = {}
    for craft_id, nested in value.items():
        if not isinstance(craft_id, str):
            continue
        parsed[craft_id] = _safe_str_int_map(nested)
    return parsed


def _safe_str_float_map(value: object) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    parsed: Dict[str, float] = {}
    for key, raw_amount in value.items():
        if isinstance(key, str):
            parsed[key] = max(0.0, _safe_float(raw_amount))
    return parsed


def _extract_str_set(value: object) -> Set[str]:
    if not isinstance(value, (list, set, tuple)):
        return set()
    return {
        item
        for item in value
        if isinstance(item, str)
    }


def _increment_nested_counter(store: Dict[str, Dict[str, int]], craft_id: str, key: str) -> None:
    craft_store = store.setdefault(craft_id, {})
    craft_store[key] = craft_store.get(key, 0) + 1


def _delivered_fish_count(progress: CraftingProgress, craft_id: str, fish_name: str) -> int:
    delivered = progress.delivered_fish_counts_by_craft.get(craft_id, {})
    if fish_name:
        return _count_name_case_insensitive(delivered, fish_name)
    return sum(delivered.values())


def _delivered_mutation_count(progress: CraftingProgress, craft_id: str, mutation_name: str) -> int:
    delivered = progress.delivered_mutation_counts_by_craft.get(craft_id, {})
    if mutation_name:
        return delivered.get(mutation_name, 0)
    return sum(delivered.values())


def _delivered_fish_with_mutation_count(
    progress: CraftingProgress,
    craft_id: str,
    fish_name: str,
    mutation_name: str,
) -> int:
    delivered = progress.delivered_fish_with_mutation_pair_counts_by_craft.get(craft_id, {})
    if fish_name and mutation_name:
        return _count_fish_mutation_pair(
            delivered,
            fish_name=fish_name,
            mutation_name=mutation_name,
        )
    if fish_name:
        return _count_fish_mutation_pair(delivered, fish_name=fish_name, mutation_name=None)
    if mutation_name:
        return _count_fish_mutation_pair(delivered, fish_name=None, mutation_name=mutation_name)
    return sum(delivered.values())


def _fish_name_matches(actual_name: str, expected_name: str) -> bool:
    return fish_name_matches(actual_name, expected_name)


def _count_name_case_insensitive(counts: Dict[str, int], name: str) -> int:
    return count_name_case_insensitive(counts, name)


def _count_fish_mutation_pair(
    counts: Dict[str, int],
    *,
    fish_name: Optional[str],
    mutation_name: Optional[str],
) -> int:
    return count_fish_mutation_pair(
        counts,
        fish_name=fish_name,
        mutation_name=mutation_name,
    )


def _fish_mutation_key(fish_name: str, mutation_name: str) -> str:
    return fish_mutation_key(fish_name, mutation_name)


def _seconds_from_requirement(requirement: Dict[str, object]) -> float:
    return seconds_from_requirement(requirement, clamp_non_negative=True)
