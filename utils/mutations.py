import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Mutation:
    name: str
    description: str
    xp_multiplier: float
    gold_multiplier: float
    chance: float


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
        with mutation_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        name = data.get("name")
        if not name:
            continue

        chance = _normalize_chance(data.get("chance"), data.get("chance_percent"))

        mutations.append(
            Mutation(
                name=name,
                description=data.get("description", ""),
                xp_multiplier=float(data.get("xp_multiplier", 1.0)),
                gold_multiplier=float(data.get("gold_multiplier", 1.0)),
                chance=chance,
            )
        )

    if not mutations:
        raise RuntimeError("Nenhuma mutação encontrada. Verifique os arquivos em /mutations.")

    return mutations


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
