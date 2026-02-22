from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BaitDefinition:
    bait_id: str
    crate_id: str
    name: str
    control: float
    luck: float
    kg_plus: float
    rarity: str


@dataclass(frozen=True)
class BaitCrateDefinition:
    crate_id: str
    name: str
    price: float
    roll_min: int
    roll_max: int
    rarity_chances: Dict[str, float]
    baits: Tuple[BaitDefinition, ...]

    def expected_rolls(self) -> float:
        return (self.roll_min + self.roll_max) / 2

    def choose_bait(self) -> Optional[BaitDefinition]:
        if not self.baits:
            return None

        baits_by_rarity: Dict[str, List[BaitDefinition]] = {}
        for bait in self.baits:
            baits_by_rarity.setdefault(bait.rarity, []).append(bait)

        available_rarities = list(baits_by_rarity.keys())
        if not available_rarities:
            return None

        weights = [self.rarity_chances.get(rarity, 0.0) for rarity in available_rarities]
        if sum(weights) <= 0:
            weights = [1.0 for _ in available_rarities]

        selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
        return random.choice(baits_by_rarity[selected_rarity])

    def open_crate(self) -> List[BaitDefinition]:
        drops: List[BaitDefinition] = []
        for _ in range(random.randint(self.roll_min, self.roll_max)):
            bait = self.choose_bait()
            if bait is not None:
                drops.append(bait)
        return drops


def load_bait_crates(base_dir: Path) -> List[BaitCrateDefinition]:
    if not base_dir.exists():
        return []

    crates: List[BaitCrateDefinition] = []
    for crate_dir in sorted(path for path in base_dir.iterdir() if path.is_dir()):
        config_path = crate_dir / f"{crate_dir.name}.json"
        if not config_path.exists():
            json_candidates = sorted(crate_dir.glob("*.json"))
            if len(json_candidates) != 1:
                continue
            config_path = json_candidates[0]

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: caixa de isca ignorada ({config_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: caixa de isca ignorada ({config_path}): formato invalido.")
            continue

        crate_id = crate_dir.name
        baits = _load_baits_for_crate(crate_id, crate_dir / "baits")
        if not baits:
            print(f"Aviso: caixa de isca sem iscas validas ({crate_id}).")
            continue

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            print(f"Aviso: caixa de isca sem nome valido ({config_path}).")
            continue

        try:
            price = float(data.get("price", 0.0))
            roll_min = int(data.get("roll_min", 3))
            roll_max = int(data.get("roll_max", 7))
        except (TypeError, ValueError):
            print(f"Aviso: caixa de isca com valores invalidos ({config_path}).")
            continue

        price = max(0.0, price)
        roll_min = max(1, roll_min)
        roll_max = max(1, roll_max)
        if roll_min > roll_max:
            roll_min, roll_max = roll_max, roll_min

        raw_rarity_chances = data.get("rarity_chances")
        rarity_chances: Dict[str, float] = {}
        if isinstance(raw_rarity_chances, dict):
            for rarity, raw_weight in raw_rarity_chances.items():
                if not isinstance(rarity, str) or not rarity:
                    continue
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if weight > 0:
                    rarity_chances[rarity] = weight

        crates.append(
            BaitCrateDefinition(
                crate_id=crate_id,
                name=name.strip(),
                price=price,
                roll_min=roll_min,
                roll_max=roll_max,
                rarity_chances=rarity_chances,
                baits=tuple(baits),
            )
        )

    return crates


def build_bait_lookup(crates: List[BaitCrateDefinition]) -> Dict[str, BaitDefinition]:
    lookup: Dict[str, BaitDefinition] = {}
    for crate in crates:
        for bait in crate.baits:
            lookup[bait.bait_id] = bait
    return lookup


def _load_baits_for_crate(crate_id: str, baits_dir: Path) -> List[BaitDefinition]:
    if not baits_dir.exists():
        return []

    baits: List[BaitDefinition] = []
    for bait_path in sorted(baits_dir.glob("*.json")):
        try:
            with bait_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: isca ignorada ({bait_path}): {exc}")
            continue

        if not isinstance(data, dict):
            print(f"Aviso: isca ignorada ({bait_path}): formato invalido.")
            continue

        required_fields = ("name", "control", "luck", "kg_plus", "rarity")
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print(
                "Aviso: isca ignorada "
                f"({bait_path}): campos obrigatorios ausentes ({', '.join(missing_fields)})."
            )
            continue

        raw_name = data.get("name")
        raw_rarity = data.get("rarity")
        if not isinstance(raw_name, str) or not raw_name.strip():
            print(f"Aviso: isca ignorada ({bait_path}): name invalido.")
            continue
        if not isinstance(raw_rarity, str) or not raw_rarity.strip():
            print(f"Aviso: isca ignorada ({bait_path}): rarity invalida.")
            continue

        try:
            control = float(data.get("control"))
            luck = float(data.get("luck"))
            kg_plus = float(data.get("kg_plus"))
        except (TypeError, ValueError):
            print(f"Aviso: isca ignorada ({bait_path}): valores numericos invalidos.")
            continue

        raw_id = data.get("id", bait_path.stem)
        bait_key = raw_id.strip() if isinstance(raw_id, str) else bait_path.stem
        if not bait_key:
            bait_key = bait_path.stem
        bait_id = f"{crate_id}/{bait_key}"

        baits.append(
            BaitDefinition(
                bait_id=bait_id,
                crate_id=crate_id,
                name=raw_name.strip(),
                control=control,
                luck=luck,
                kg_plus=kg_plus,
                rarity=raw_rarity.strip(),
            )
        )

    return baits
