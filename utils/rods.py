import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


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
    can_slam: bool = False
    slam_chance: float = 0.0
    slam_time_bonus: float = 0.0
    unlocked_default: bool = False
    unlocks_with_pool: str = ""


def load_rods(base_dir: Path) -> List[Rod]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de varas não encontrado: {base_dir}")

    rods: List[Rod] = []
    for rod_path in sorted(base_dir.glob("*.json")):
        with rod_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        name = data.get("name")
        if not name:
            continue
        raw_unlocks_with_pool = data.get("unlockswithpool", data.get("unlocks_with_pool", ""))
        unlocks_with_pool = (
            raw_unlocks_with_pool.strip()
            if isinstance(raw_unlocks_with_pool, str)
            else ""
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
                slash_chance=float(data.get("slash_chance", 0.0)),
                can_slam=bool(data.get("can_slam", False)),
                slam_chance=float(data.get("slam_chance", 0.0)),
                slam_time_bonus=float(data.get("slam_time_bonus", 0.0)),
                unlocked_default=bool(data.get("unlocked_default", False)),
                unlocks_with_pool=unlocks_with_pool,
            )
        )

    if not rods:
        raise RuntimeError("Nenhuma vara encontrada. Verifique os arquivos em /rods.")

    return rods
