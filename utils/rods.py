import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


def _normalize_probability(raw_value: object) -> float:
    try:
        chance = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    if chance > 1.0:
        chance /= 100.0
    return max(0.0, min(1.0, chance))


@dataclass(frozen=True)
class Rod:
    name: str
    luck: float
    kg_max: float
    control: float
    description: str
    price: float
    can_slash: bool = False
    slash_chance: float = 0.0
    slash_power: int = 1
    can_slam: bool = False
    slam_chance: float = 0.0
    slam_time_bonus: float = 0.0
    can_recover: bool = False
    recover_chance: float = 0.0
    can_dupe: bool = False
    dupe_chance: float = 0.0
    can_alter: bool = False
    timecount: float = 0.0
    hardcount: float = 0.0
    unlocked_default: bool = False
    unlocks_with_pool: str = ""
    counts_for_bestiary_completion: bool = True


def load_rods(base_dir: Path) -> List[Rod]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de varas não encontrado: {base_dir}")

    rods: List[Rod] = []
    for rod_path in sorted(base_dir.glob("*.json")):
        try:
            with rod_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: vara ignorada ({rod_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: vara ignorada ({rod_path}): formato invalido.")
            continue

        name = data.get("name")
        if not name:
            continue
        raw_unlocks_with_pool = data.get("unlockswithpool", data.get("unlocks_with_pool", ""))
        unlocks_with_pool = (
            raw_unlocks_with_pool.strip()
            if isinstance(raw_unlocks_with_pool, str)
            else ""
        )
        raw_counts_flag = data.get("counts_for_bestiary_completion")
        if isinstance(raw_counts_flag, bool):
            counts_for_bestiary_completion = raw_counts_flag
        else:
            counts_for_bestiary_completion = not bool(
                data.get("exclude_from_bestiary_completion", False)
            )

        rods.append(
            Rod(
                name=name,
                luck=float(data.get("luck", 0.0)),
                kg_max=float(data.get("kg_max", 0.0)),
                control=float(data.get("control", 0.0)),
                description=data.get("description", ""),
                price=float(data.get("price", 0.0)),
                can_slash=bool(data.get("can_slash", False)),
                slash_chance=_normalize_probability(data.get("slash_chance", 0.0)),
                slash_power=max(1, int(data.get("slash_power", 1))),
                can_slam=bool(data.get("can_slam", False)),
                slam_chance=_normalize_probability(data.get("slam_chance", 0.0)),
                slam_time_bonus=float(data.get("slam_time_bonus", 0.0)),
                can_recover=bool(data.get("can_recover", False)),
                recover_chance=_normalize_probability(data.get("recover_chance", 0.0)),
                can_dupe=bool(data.get("can_dupe", False)),
                dupe_chance=_normalize_probability(data.get("dupe_chance", 0.0)),
                can_alter=bool(data.get("can_alter", False)),
                timecount=float(data.get("timecount", data.get("time_count", 0.0))),
                hardcount=float(data.get("hardcount", data.get("hard_count", 0.0))),
                unlocked_default=bool(data.get("unlocked_default", False)),
                unlocks_with_pool=unlocks_with_pool,
                counts_for_bestiary_completion=counts_for_bestiary_completion,
            )
        )

    if not rods:
        raise RuntimeError("Nenhuma vara encontrada. Verifique os arquivos em /rods.")

    return rods
