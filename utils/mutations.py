import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    xp_multiplier: float
    gold_multiplier: float
    chance: float
    required_rods: Tuple[str, ...]
    rod_chance_overrides: Tuple[Tuple[str, float], ...] = ()


def _normalize_chance(raw_chance: object, raw_percent: object) -> float:
    if raw_chance is not None:
        try:
            chance = float(raw_chance)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, chance)
    try:
        chance_percent = float(raw_percent)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, chance_percent / 100)


def _parse_required_rods(raw_required_rods: object) -> Tuple[str, ...]:
    if isinstance(raw_required_rods, list):
        return tuple(
            rod_name.strip()
            for rod_name in raw_required_rods
            if isinstance(rod_name, str) and rod_name.strip()
        )
    if isinstance(raw_required_rods, str) and raw_required_rods.strip():
        return (raw_required_rods.strip(),)
    return ()


def _parse_rod_chance_overrides(raw: object) -> Tuple[Tuple[str, float], ...]:
    if not isinstance(raw, dict):
        return ()
    result = []
    for rod_name, chance_val in raw.items():
        if isinstance(rod_name, str) and rod_name.strip():
            try:
                chance = float(chance_val) / 100.0
            except (TypeError, ValueError):
                continue
            result.append((rod_name.strip(), max(0.0, chance)))
    return tuple(result)


def _load_mutations_from_directory(base_dir: Path) -> List[Mutation]:
    mutations: List[Mutation] = []
    for mutation_path in sorted(base_dir.glob("*.json")):
        try:
            with mutation_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: mutacao ignorada ({mutation_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: mutacao ignorada ({mutation_path}): formato invalido.")
            continue

        name = data.get("name")
        if not name:
            continue

        chance = _normalize_chance(data.get("chance"), data.get("chance_percent"))
        required_rods = _parse_required_rods(data.get("required_rods"))
        rod_chance_overrides = _parse_rod_chance_overrides(
            data.get("rod_chance_overrides")
        )

        mutations.append(
            Mutation(
                name=name,
                description=data.get("description", ""),
                xp_multiplier=float(data.get("xp_multiplier", 1.0)),
                gold_multiplier=float(data.get("gold_multiplier", 1.0)),
                chance=chance,
                required_rods=required_rods,
                rod_chance_overrides=rod_chance_overrides,
            )
        )
    return mutations


def _load_mutations(
    base_dir: Path,
    *,
    allow_missing_directory: bool,
    require_non_empty: bool,
) -> List[Mutation]:
    if not base_dir.exists():
        if allow_missing_directory:
            return []
        raise FileNotFoundError(f"Diretório de mutações não encontrado: {base_dir}")

    mutations = _load_mutations_from_directory(base_dir)
    if require_non_empty and not mutations:
        raise RuntimeError("Nenhuma mutação encontrada. Verifique os arquivos em /mutations.")
    return mutations


def load_mutations(base_dir: Path) -> List[Mutation]:
    return _load_mutations(
        base_dir,
        allow_missing_directory=False,
        require_non_empty=True,
    )


def load_mutations_optional(base_dir: Path) -> List[Mutation]:
    return _load_mutations(
        base_dir,
        allow_missing_directory=True,
        require_non_empty=False,
    )

def filter_mutations_for_rod(
    mutations: Sequence[Mutation],
    rod_name: str,
) -> List[Mutation]:
    normalized_rod_name = rod_name.casefold()
    result: List[Mutation] = []
    for mutation in mutations:
        if mutation.required_rods and normalized_rod_name not in {
            r.casefold() for r in mutation.required_rods
        }:
            continue
        # Apply rod-specific chance override if present
        override_chance: Optional[float] = None
        for override_rod, override_val in mutation.rod_chance_overrides:
            if override_rod.casefold() == normalized_rod_name:
                override_chance = override_val
                break
        if override_chance is not None:
            mutation = Mutation(
                name=mutation.name,
                description=mutation.description,
                xp_multiplier=mutation.xp_multiplier,
                gold_multiplier=mutation.gold_multiplier,
                chance=override_chance,
                required_rods=mutation.required_rods,
                rod_chance_overrides=mutation.rod_chance_overrides,
            )
        result.append(mutation)
    return result


def filter_mutations_for_appraisal(
    mutations: Sequence[Mutation],
) -> List[Mutation]:
    return [mutation for mutation in mutations if not mutation.required_rods]


def choose_mutation(mutations: List[Mutation]) -> Optional[Mutation]:
    available = [mutation for mutation in mutations if mutation.chance > 0]
    if not available:
        return None

    total_chance = sum(mutation.chance for mutation in available)
    if total_chance <= 0:
        return None

    roll = random.random()
    if roll > total_chance:
        return None

    weights = [mutation.chance for mutation in available]
    return random.choices(available, weights=weights, k=1)[0]
