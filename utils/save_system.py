import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

from utils.inventory import InventoryEntry
from utils.rods import Rod

if TYPE_CHECKING:
    from utils.pesca import FishingPool


SAVE_VERSION = 1
SAVE_FILE_NAME = "savegame.json"


def get_default_save_path() -> Path:
    return Path(__file__).resolve().parent.parent / SAVE_FILE_NAME


def serialize_inventory(inventory: Sequence[InventoryEntry]) -> List[Dict[str, object]]:
    return [
        {
            "name": entry.name,
            "rarity": entry.rarity,
            "kg": entry.kg,
            "base_value": entry.base_value,
        }
        for entry in inventory
    ]


def save_game(
    save_path: Path,
    *,
    balance: float,
    inventory: Sequence[InventoryEntry],
    owned_rods: Sequence[Rod],
    equipped_rod: Rod,
    selected_pool: "FishingPool",
    unlocked_pools: Sequence[str],
) -> None:
    data = {
        "version": SAVE_VERSION,
        "balance": balance,
        "inventory": serialize_inventory(inventory),
        "owned_rods": [rod.name for rod in owned_rods],
        "equipped_rod": equipped_rod.name,
        "selected_pool": selected_pool.name,
        "unlocked_pools": list(unlocked_pools),
    }
    save_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_game(save_path: Path) -> Optional[Dict[str, object]]:
    if not save_path.exists():
        return None
    try:
        raw = json.loads(save_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def restore_inventory(raw_inventory: object) -> List[InventoryEntry]:
    if not isinstance(raw_inventory, list):
        return []

    restored: List[InventoryEntry] = []
    for item in raw_inventory:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        rarity = item.get("rarity", "")
        if not isinstance(rarity, str):
            rarity = ""
        try:
            kg = float(item.get("kg", 0.0))
            base_value = float(item.get("base_value", 0.0))
        except (TypeError, ValueError):
            continue
        restored.append(
            InventoryEntry(
                name=name,
                rarity=rarity,
                kg=kg,
                base_value=base_value,
            )
        )
    return restored


def restore_owned_rods(
    raw_rods: object,
    available_rods: Sequence[Rod],
    starter_rod: Rod,
) -> List[Rod]:
    rod_by_name = {rod.name: rod for rod in available_rods}
    if not isinstance(raw_rods, list):
        return [starter_rod]

    restored: List[Rod] = []
    for name in raw_rods:
        if not isinstance(name, str):
            continue
        rod = rod_by_name.get(name)
        if rod and rod.name not in {r.name for r in restored}:
            restored.append(rod)

    if not restored:
        restored.append(starter_rod)

    return restored


def restore_selected_pool(
    raw_pool: object,
    pools: Sequence["FishingPool"],
    fallback_pool: "FishingPool",
) -> "FishingPool":
    if isinstance(raw_pool, str):
        for pool in pools:
            if pool.name == raw_pool:
                return pool
    return fallback_pool


def restore_unlocked_pools(
    raw_pools: object,
    pools: Sequence["FishingPool"],
    selected_pool: "FishingPool",
) -> List[str]:
    pool_names = {pool.name for pool in pools}
    restored: List[str] = []
    if isinstance(raw_pools, list):
        for name in raw_pools:
            if isinstance(name, str) and name in pool_names and name not in restored:
                restored.append(name)

    if selected_pool.name not in restored:
        restored.append(selected_pool.name)

    return restored


def restore_equipped_rod(
    raw_equipped: object,
    owned_rods: Sequence[Rod],
    starter_rod: Rod,
) -> Rod:
    if isinstance(raw_equipped, str):
        for rod in owned_rods:
            if rod.name == raw_equipped:
                return rod
    return starter_rod


def restore_balance(raw_balance: object, fallback: float) -> float:
    try:
        return float(raw_balance)
    except (TypeError, ValueError):
        return fallback
