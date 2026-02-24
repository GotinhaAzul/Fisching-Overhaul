from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set


BESTIARY_REWARD_TYPE_FISH = "fish_bestiary"
BESTIARY_REWARD_TYPE_RODS = "rods_bestiary"
BESTIARY_REWARD_TYPE_POOLS = "pools_bestiary"
BESTIARY_REWARD_TYPES = {
    BESTIARY_REWARD_TYPE_FISH,
    BESTIARY_REWARD_TYPE_RODS,
    BESTIARY_REWARD_TYPE_POOLS,
}
FISH_TARGET_ALL = "All"


@dataclass(frozen=True)
class BestiaryRewardDefinition:
    reward_id: str
    name: str
    trigger_type: str
    threshold_percent: float
    target_pool: str
    rewards: List[Dict[str, object]]

    @property
    def category(self) -> str:
        if self.trigger_type == BESTIARY_REWARD_TYPE_FISH:
            return "fish"
        if self.trigger_type == BESTIARY_REWARD_TYPE_RODS:
            return "rods"
        return "pools"


@dataclass
class BestiaryRewardState:
    claimed: Set[str] = field(default_factory=set)


def load_bestiary_rewards(base_dir: Path) -> List[BestiaryRewardDefinition]:
    if not base_dir.exists():
        return []

    rewards: List[BestiaryRewardDefinition] = []
    for reward_path in sorted(base_dir.glob("**/*.json")):
        try:
            with reward_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: recompensa de bestiario ignorada ({reward_path}): {exc}")
            continue

        if not isinstance(data, dict):
            print(f"Aviso: recompensa de bestiario ignorada ({reward_path}): formato invalido.")
            continue

        reward_id = data.get("id", reward_path.stem)
        if not isinstance(reward_id, str) or not reward_id.strip():
            continue

        trigger = data.get("trigger")
        if not isinstance(trigger, dict):
            continue
        trigger_type = trigger.get("type")
        if not isinstance(trigger_type, str) or trigger_type not in BESTIARY_REWARD_TYPES:
            continue

        threshold_percent = _safe_float(trigger.get("threshold_percent"), 100.0)
        threshold_percent = max(0.0, min(100.0, threshold_percent))
        target_pool = _parse_target_pool(trigger)
        rewards_payload = data.get("rewards", [])
        if not isinstance(rewards_payload, list):
            rewards_payload = []

        rewards.append(
            BestiaryRewardDefinition(
                reward_id=reward_id.strip(),
                name=str(data.get("name", reward_id)).strip() or reward_id.strip(),
                trigger_type=trigger_type,
                threshold_percent=threshold_percent,
                target_pool=target_pool,
                rewards=[item for item in rewards_payload if isinstance(item, dict)],
            )
        )
    return rewards


def serialize_bestiary_reward_state(state: BestiaryRewardState) -> Dict[str, object]:
    return {
        "claimed": sorted(state.claimed),
    }


def restore_bestiary_reward_state(
    raw_state: object,
    reward_definitions: Sequence[BestiaryRewardDefinition],
) -> BestiaryRewardState:
    known_ids = {reward.reward_id for reward in reward_definitions}
    state = BestiaryRewardState()
    if not isinstance(raw_state, dict):
        return state
    raw_claimed = raw_state.get("claimed")
    if not isinstance(raw_claimed, list):
        return state
    for reward_id in raw_claimed:
        if isinstance(reward_id, str) and reward_id in known_ids:
            state.claimed.add(reward_id)
    return state


def get_claimable_bestiary_rewards(
    reward_definitions: Sequence[BestiaryRewardDefinition],
    reward_state: BestiaryRewardState,
    *,
    category: str,
    fish_global_percent: float,
    fish_percent_by_pool: Dict[str, float],
    rods_percent: float,
    pools_percent: float,
) -> List[BestiaryRewardDefinition]:
    normalized_by_pool = {
        pool_name.casefold(): percent
        for pool_name, percent in fish_percent_by_pool.items()
        if isinstance(pool_name, str)
    }
    claimable: List[BestiaryRewardDefinition] = []
    for reward in reward_definitions:
        if reward.category != category:
            continue
        if reward.reward_id in reward_state.claimed:
            continue
        if _is_reward_eligible(
            reward,
            fish_global_percent=fish_global_percent,
            fish_percent_by_pool=normalized_by_pool,
            rods_percent=rods_percent,
            pools_percent=pools_percent,
        ):
            claimable.append(reward)
    return claimable


def _is_reward_eligible(
    reward: BestiaryRewardDefinition,
    *,
    fish_global_percent: float,
    fish_percent_by_pool: Dict[str, float],
    rods_percent: float,
    pools_percent: float,
) -> bool:
    if reward.trigger_type == BESTIARY_REWARD_TYPE_FISH:
        if reward.target_pool.casefold() == FISH_TARGET_ALL.casefold():
            return fish_global_percent >= reward.threshold_percent
        pool_percent = fish_percent_by_pool.get(reward.target_pool.casefold())
        return pool_percent is not None and pool_percent >= reward.threshold_percent
    if reward.trigger_type == BESTIARY_REWARD_TYPE_RODS:
        return rods_percent >= reward.threshold_percent
    if reward.trigger_type == BESTIARY_REWARD_TYPE_POOLS:
        return pools_percent >= reward.threshold_percent
    return False


def _parse_target_pool(trigger: Dict[str, object]) -> str:
    target = trigger.get("target")
    if isinstance(target, dict):
        pool_name = target.get("pool")
        if isinstance(pool_name, str) and pool_name.strip():
            return pool_name.strip()
    pool_name = trigger.get("pool")
    if isinstance(pool_name, str) and pool_name.strip():
        return pool_name.strip()
    return FISH_TARGET_ALL


def _safe_float(raw_value: object, fallback: float) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return fallback
