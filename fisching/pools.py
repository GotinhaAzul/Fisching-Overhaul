from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from fisching.models import Fish, Pool


def load_pools(base_path: Path | None = None) -> Dict[str, Pool]:
    if base_path is None:
        base_path = Path(__file__).resolve().parent / "pools"

    pools: Dict[str, Pool] = {}
    if not base_path.exists():
        return pools

    for pool_dir in sorted(path for path in base_path.iterdir() if path.is_dir()):
        pool_file = pool_dir / "pool.json"
        if not pool_file.exists():
            continue

        pool_data = json.loads(pool_file.read_text(encoding="utf-8"))
        fish: Dict[str, Fish] = {}

        for fish_file in sorted(pool_dir.glob("*.json")):
            if fish_file.name == "pool.json":
                continue

            fish_data = json.loads(fish_file.read_text(encoding="utf-8"))
            fish_id = fish_file.stem
            fish[fish_id] = Fish(
                name=fish_data["name"],
                rarity=fish_data["rarity"],
                weight_kg=float(fish_data["weight_kg"]),
                base_value=int(fish_data["base_value"]),
                resilience=int(fish_data["resilience"]),
                description=fish_data["description"],
            )

        rarity_chances = pool_data["rarity_chances"]
        pools[pool_dir.name] = Pool(
            name=pool_data["name"],
            description=pool_data["description"],
            fish=fish,
            rarity_chances=rarity_chances,
        )

    return pools
