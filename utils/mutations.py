import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    xp_multiplier: float
    gold_multiplier: float
    chance: float
    required_rods: Tuple[str, ...]


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


def load_mutations(base_dir: Path) -> List[Mutation]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de mutações não encontrado: {base_dir}")

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

        raw_required_rods = data.get("required_rods")
        if isinstance(raw_required_rods, list):
            required_rods = tuple(
                rod_name.strip()
                for rod_name in raw_required_rods
                if isinstance(rod_name, str) and rod_name.strip()
            )
        elif isinstance(raw_required_rods, str) and raw_required_rods.strip():
            required_rods = (raw_required_rods.strip(),)
        else:
            required_rods = ()

        mutations.append(
            Mutation(
                name=name,
                description=data.get("description", ""),
                xp_multiplier=float(data.get("xp_multiplier", 1.0)),
                gold_multiplier=float(data.get("gold_multiplier", 1.0)),
                chance=chance,
                required_rods=required_rods,
            )
        )

    if not mutations:
        raise RuntimeError("Nenhuma mutação encontrada. Verifique os arquivos em /mutations.")

    return mutations


def load_mutations_optional(base_dir: Path) -> List[Mutation]:
    if not base_dir.exists():
        return []

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

        raw_required_rods = data.get("required_rods")
        if isinstance(raw_required_rods, list):
            required_rods = tuple(
                rod_name.strip()
                for rod_name in raw_required_rods
                if isinstance(rod_name, str) and rod_name.strip()
            )
        elif isinstance(raw_required_rods, str) and raw_required_rods.strip():
            required_rods = (raw_required_rods.strip(),)
        else:
            required_rods = ()

        mutations.append(
            Mutation(
                name=name,
                description=data.get("description", ""),
                xp_multiplier=float(data.get("xp_multiplier", 1.0)),
                gold_multiplier=float(data.get("gold_multiplier", 1.0)),
                chance=chance,
                required_rods=required_rods,
            )
        )

    return mutations


def filter_mutations_for_rod(
    mutations: Sequence[Mutation],
    rod_name: str,
) -> List[Mutation]:
    normalized_rod_name = rod_name.casefold()
    return [
        mutation
        for mutation in mutations
        if not mutation.required_rods
        or normalized_rod_name
        in {required_rod.casefold() for required_rod in mutation.required_rods}
    ]


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
