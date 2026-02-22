from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, TYPE_CHECKING

from utils.inventory import InventoryEntry
from utils.levels import apply_xp_gain
from utils.ui import clear_screen, print_spaced_lines

if TYPE_CHECKING:
    from utils.pesca import FishProfile, FishingPool


@dataclass
class MissionDefinition:
    mission_id: str
    name: str
    description: str
    requirements: List[Dict[str, object]]
    rewards: List[Dict[str, object]]
    starts_unlocked: bool = False


@dataclass
class MissionState:
    unlocked: Set[str] = field(default_factory=set)
    completed: Set[str] = field(default_factory=set)
    claimed: Set[str] = field(default_factory=set)
    unlocked_progress_baselines: Dict[str, Dict[str, object]] = field(default_factory=dict)
    unlocked_completed_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class MissionProgress:
    total_money_earned: float = 0.0
    total_money_spent: float = 0.0
    fish_caught: int = 0
    fish_delivered: int = 0
    fish_sold: int = 0
    mutated_fish_caught: int = 0
    mutated_fish_delivered: int = 0
    fish_caught_by_name: Dict[str, int] = field(default_factory=dict)
    fish_delivered_by_name: Dict[str, int] = field(default_factory=dict)
    fish_sold_by_name: Dict[str, int] = field(default_factory=dict)
    fish_caught_with_mutation_by_name: Dict[str, int] = field(default_factory=dict)
    fish_delivered_with_mutation_by_name: Dict[str, int] = field(default_factory=dict)
    fish_delivered_with_mutation_pair_counts: Dict[str, int] = field(default_factory=dict)
    mutations_caught_by_name: Dict[str, int] = field(default_factory=dict)
    mutations_delivered_by_name: Dict[str, int] = field(default_factory=dict)
    play_time_seconds: float = 0.0

    def record_money_earned(self, amount: float) -> None:
        if amount > 0:
            self.total_money_earned += amount

    def record_money_spent(self, amount: float) -> None:
        if amount > 0:
            self.total_money_spent += amount

    def record_fish_caught(self, fish_name: str, mutation_name: Optional[str]) -> None:
        self.fish_caught += 1
        self.fish_caught_by_name[fish_name] = self.fish_caught_by_name.get(fish_name, 0) + 1
        if mutation_name:
            self.mutated_fish_caught += 1
            self.fish_caught_with_mutation_by_name[fish_name] = (
                self.fish_caught_with_mutation_by_name.get(fish_name, 0) + 1
            )
            self.mutations_caught_by_name[mutation_name] = (
                self.mutations_caught_by_name.get(mutation_name, 0) + 1
            )

    def record_fish_delivered(self, fish_name: str, mutation_name: Optional[str]) -> None:
        self.fish_delivered += 1
        self.fish_delivered_by_name[fish_name] = self.fish_delivered_by_name.get(fish_name, 0) + 1
        if mutation_name:
            self.mutated_fish_delivered += 1
            self.fish_delivered_with_mutation_by_name[fish_name] = (
                self.fish_delivered_with_mutation_by_name.get(fish_name, 0) + 1
            )
            self.mutations_delivered_by_name[mutation_name] = (
                self.mutations_delivered_by_name.get(mutation_name, 0) + 1
            )
            pair_key = _fish_mutation_key(fish_name, mutation_name)
            self.fish_delivered_with_mutation_pair_counts[pair_key] = (
                self.fish_delivered_with_mutation_pair_counts.get(pair_key, 0) + 1
            )

    def record_fish_sold(self, fish_name: str) -> None:
        self.fish_sold += 1
        self.fish_sold_by_name[fish_name] = self.fish_sold_by_name.get(fish_name, 0) + 1

    def add_play_time(self, seconds: float) -> None:
        if seconds > 0:
            self.play_time_seconds += seconds


def serialize_mission_state(state: MissionState) -> Dict[str, object]:
    return {
        "unlocked": sorted(state.unlocked),
        "completed": sorted(state.completed),
        "claimed": sorted(state.claimed),
        "unlocked_progress_baselines": {
            mission_id: state.unlocked_progress_baselines.get(mission_id, {})
            for mission_id in sorted(state.unlocked)
        },
        "unlocked_completed_counts": {
            mission_id: state.unlocked_completed_counts.get(mission_id, 0)
            for mission_id in sorted(state.unlocked)
        },
    }


def restore_mission_state(raw_state: object, missions: Sequence[MissionDefinition]) -> MissionState:
    mission_ids = {mission.mission_id for mission in missions}
    state = MissionState()
    if isinstance(raw_state, dict):
        for key, target in (
            ("unlocked", state.unlocked),
            ("completed", state.completed),
            ("claimed", state.claimed),
        ):
            raw_list = raw_state.get(key)
            if isinstance(raw_list, list):
                for mission_id in raw_list:
                    if isinstance(mission_id, str) and mission_id in mission_ids:
                        target.add(mission_id)
        raw_progress_baselines = raw_state.get("unlocked_progress_baselines")
        if isinstance(raw_progress_baselines, dict):
            for mission_id, raw_baseline in raw_progress_baselines.items():
                if (
                    isinstance(mission_id, str)
                    and mission_id in mission_ids
                    and isinstance(raw_baseline, dict)
                ):
                    state.unlocked_progress_baselines[mission_id] = serialize_mission_progress(
                        restore_mission_progress(raw_baseline)
                    )
        raw_completed_counts = raw_state.get("unlocked_completed_counts")
        if isinstance(raw_completed_counts, dict):
            for mission_id, raw_count in raw_completed_counts.items():
                if isinstance(mission_id, str) and mission_id in mission_ids:
                    state.unlocked_completed_counts[mission_id] = max(0, _safe_int(raw_count))
    default_unlocked = {
        mission.mission_id
        for mission in missions
        if mission.starts_unlocked
    }
    if state.unlocked:
        state.unlocked.update(default_unlocked)
    else:
        state.unlocked = default_unlocked
    for mission_id in state.unlocked:
        state.unlocked_progress_baselines.setdefault(mission_id, {})
        state.unlocked_completed_counts.setdefault(mission_id, 0)
    return state


def serialize_mission_progress(progress: MissionProgress) -> Dict[str, object]:
    return {
        "total_money_earned": progress.total_money_earned,
        "total_money_spent": progress.total_money_spent,
        "fish_caught": progress.fish_caught,
        "fish_delivered": progress.fish_delivered,
        "fish_sold": progress.fish_sold,
        "mutated_fish_caught": progress.mutated_fish_caught,
        "mutated_fish_delivered": progress.mutated_fish_delivered,
        # Snapshot maps to avoid mission baselines sharing mutable dict references.
        "fish_caught_by_name": dict(progress.fish_caught_by_name),
        "fish_delivered_by_name": dict(progress.fish_delivered_by_name),
        "fish_sold_by_name": dict(progress.fish_sold_by_name),
        "fish_caught_with_mutation_by_name": dict(progress.fish_caught_with_mutation_by_name),
        "fish_delivered_with_mutation_by_name": dict(progress.fish_delivered_with_mutation_by_name),
        "fish_delivered_with_mutation_pair_counts": dict(progress.fish_delivered_with_mutation_pair_counts),
        "mutations_caught_by_name": dict(progress.mutations_caught_by_name),
        "mutations_delivered_by_name": dict(progress.mutations_delivered_by_name),
        "play_time_seconds": progress.play_time_seconds,
    }


def restore_mission_progress(raw_progress: object) -> MissionProgress:
    progress = MissionProgress()
    if not isinstance(raw_progress, dict):
        return progress
    progress.total_money_earned = _safe_float(raw_progress.get("total_money_earned"))
    progress.total_money_spent = _safe_float(raw_progress.get("total_money_spent"))
    progress.fish_caught = _safe_int(raw_progress.get("fish_caught"))
    progress.fish_delivered = _safe_int(raw_progress.get("fish_delivered"))
    progress.fish_sold = _safe_int(raw_progress.get("fish_sold"))
    progress.mutated_fish_caught = _safe_int(raw_progress.get("mutated_fish_caught"))
    progress.mutated_fish_delivered = _safe_int(raw_progress.get("mutated_fish_delivered"))
    progress.fish_caught_by_name = _safe_str_int_map(raw_progress.get("fish_caught_by_name"))
    progress.fish_delivered_by_name = _safe_str_int_map(raw_progress.get("fish_delivered_by_name"))
    progress.fish_sold_by_name = _safe_str_int_map(raw_progress.get("fish_sold_by_name"))
    progress.fish_caught_with_mutation_by_name = _safe_str_int_map(
        raw_progress.get("fish_caught_with_mutation_by_name")
    )
    progress.fish_delivered_with_mutation_by_name = _safe_str_int_map(
        raw_progress.get("fish_delivered_with_mutation_by_name")
    )
    progress.fish_delivered_with_mutation_pair_counts = _safe_str_int_map(
        raw_progress.get("fish_delivered_with_mutation_pair_counts")
    )
    progress.mutations_caught_by_name = _safe_str_int_map(raw_progress.get("mutations_caught_by_name"))
    progress.mutations_delivered_by_name = _safe_str_int_map(raw_progress.get("mutations_delivered_by_name"))
    progress.play_time_seconds = _safe_float(raw_progress.get("play_time_seconds"))
    return progress


def load_missions(base_dir: Path) -> List[MissionDefinition]:
    if not base_dir.exists():
        return []

    missions: List[MissionDefinition] = []
    for mission_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        config_path = mission_dir / "mission.json"
        if not config_path.exists():
            continue

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: missao ignorada ({config_path}): {exc}")
            continue

        if not isinstance(data, dict):
            print(f"Aviso: missao ignorada ({config_path}): formato invalido.")
            continue

        mission_id = data.get("id", mission_dir.name)
        if not isinstance(mission_id, str) or not mission_id:
            continue

        requirements = data.get("requirements", [])
        rewards = data.get("rewards", [])
        if not isinstance(requirements, list):
            requirements = []
        if not isinstance(rewards, list):
            rewards = []

        missions.append(
            MissionDefinition(
                mission_id=mission_id,
                name=data.get("name", mission_id),
                description=data.get("description", ""),
                requirements=[req for req in requirements if isinstance(req, dict)],
                rewards=[reward for reward in rewards if isinstance(reward, dict)],
                starts_unlocked=bool(data.get("starts_unlocked", False)),
            )
        )

    return missions


def update_mission_completions(
    missions: Sequence[MissionDefinition],
    state: MissionState,
    progress: MissionProgress,
    *,
    level: int,
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> Set[str]:
    _sync_unlock_baselines(state)
    newly_completed: Set[str] = set()
    for mission in missions:
        if mission.mission_id not in state.unlocked:
            continue
        if mission.mission_id in state.completed:
            continue
        baseline_progress = _mission_baseline_progress(state, mission.mission_id)
        completed_baseline = state.unlocked_completed_counts.get(mission.mission_id, 0)
        if is_mission_complete(
            mission,
            progress,
            state.completed,
            baseline_progress=baseline_progress,
            completed_baseline=completed_baseline,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        ):
            state.completed.add(mission.mission_id)
            newly_completed.add(mission.mission_id)
    return newly_completed


def is_mission_complete(
    mission: MissionDefinition,
    progress: MissionProgress,
    completed_missions: Set[str],
    *,
    baseline_progress: MissionProgress,
    completed_baseline: int,
    level: int,
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> bool:
    for requirement in mission.requirements:
        if not _check_requirement(
            requirement,
            progress,
            completed_missions,
            current_mission_id=mission.mission_id,
            baseline_progress=baseline_progress,
            completed_baseline=completed_baseline,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        ):
            return False
    return True


def show_missions_menu(
    missions: Sequence[MissionDefinition],
    state: MissionState,
    progress: MissionProgress,
    *,
    level: int,
    xp: int,
    balance: float,
    inventory: List[InventoryEntry],
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
    unlocked_pools: Set[str],
    unlocked_rods: Set[str],
    available_rods: Sequence[object],
    fish_by_name: Dict[str, "FishProfile"],
) -> Tuple[int, int, float]:
    _sync_unlock_baselines(state)
    mission_by_id = {mission.mission_id: mission for mission in missions}
    while True:
        update_mission_completions(
            missions,
            state,
            progress,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        )
        ordered = sorted(
            (
                mission
                for mission in mission_by_id.values()
                if mission.mission_id in state.unlocked
                and mission.mission_id not in state.claimed
            ),
            key=lambda mission: mission.name,
        )

        clear_screen()
        print_spaced_lines([
            "📜 === Missões ===",
            f"Concluídas: {len(state.completed)} | Disponíveis: {len(ordered)}",
        ])

        if not ordered:
            print("Nenhuma missão pendente no momento.")
            input("\nEnter para voltar.")
            return level, xp, balance
        for idx, mission in enumerate(ordered, start=1):
            status = _format_mission_status(mission, state)
            print(f"{idx}. {mission.name} {status}")

        print("0. Voltar")
        choice = input("Escolha uma missão: ").strip()

        if choice == "0":
            return level, xp, balance
        if not choice.isdigit():
            print("Entrada inválida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(ordered)):
            print("Número fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        mission = ordered[idx - 1]
        baseline_progress = _mission_baseline_progress(state, mission.mission_id)
        completed_baseline = state.unlocked_completed_counts.get(mission.mission_id, 0)

        clear_screen()
        print(f"=== {mission.name} ===")
        if mission.description:
            print(mission.description)
        print("\nRequisitos:")
        for requirement in mission.requirements:
            label, current, target, done = _format_requirement(
                requirement,
                progress,
                state.completed,
                mission.mission_id,
                baseline_progress=baseline_progress,
                completed_baseline=completed_baseline,
                level=level,
                pools=pools,
                discovered_fish=discovered_fish,
            )
            status = "✅" if done else "⏳"
            print(f"- {label} ({current}/{target}) {status}")

        print("\nRecompensas:")
        visible_rewards = [
            reward
            for reward in mission.rewards
            if reward.get("type") in {"money", "xp", "fish"}
        ]
        if visible_rewards:
            for reward in visible_rewards:
                print(f"- {_format_reward(reward)}")
        else:
            print("- Recompensas ocultas")


        mission_actions = _build_mission_actions(
            mission,
            progress,
            state.completed,
            baseline_progress=baseline_progress,
            completed_baseline=completed_baseline,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        )
        can_claim_reward = mission.mission_id in state.completed and mission.mission_id not in state.claimed

        if mission_actions or can_claim_reward:
            print("\nAções:")
            action_map: Dict[str, str] = {}
            option_number = 1

            deliver_requirements = (
                mission_actions.get("deliver_fish", [])
                + mission_actions.get("deliver_mutation", [])
                + mission_actions.get("deliver_fish_with_mutation", [])
            )
            if deliver_requirements:
                key = str(option_number)
                action_map[key] = "deliver_fish"
                print(f"{key}. Entregar peixe para a missão")
                option_number += 1
            if mission_actions.get("spend_money"):
                key = str(option_number)
                action_map[key] = "spend_money"
                print(f"{key}. Pagar dinheiro para a missão")
                option_number += 1
            if can_claim_reward:
                key = str(option_number)
                action_map[key] = "claim_reward"
                print(f"{key}. Resgatar recompensa")

            print("0. Voltar")
            selection = input("Escolha uma opção: ").strip()
            action = action_map.get(selection)
            if not action:
                continue

            if action == "deliver_fish":
                if _deliver_fish_for_mission(
                    deliver_requirements,
                    inventory,
                    progress,
                ):
                    print("Peixe entregue para a missão!")
                input("\nEnter para voltar.")
                continue

            if action == "spend_money":
                amount = _request_mission_payment(
                    mission_actions["spend_money"],
                    progress,
                    baseline_progress,
                    balance,
                )
                if amount > 0:
                    balance -= amount
                    progress.record_money_spent(amount)
                    print(f"Pagamento de R$ {amount:0.2f} enviado para a missão.")
                input("\nEnter para voltar.")
                continue

            if action == "claim_reward":
                balance, level, xp, notes = apply_mission_rewards(
                    mission,
                    progress,
                    state,
                    balance=balance,
                    level=level,
                    xp=xp,
                    inventory=inventory,
                    unlocked_pools=unlocked_pools,
                    unlocked_rods=unlocked_rods,
                    available_rods=available_rods,
                    fish_by_name=fish_by_name,
                    discovered_fish=discovered_fish,
                )
                state.claimed.add(mission.mission_id)
                if notes:
                    print("\n".join(notes))
                else:
                    print("Recompensa resgatada!")
                input("\nEnter para voltar.")
            continue

        input("\nEnter para voltar.")


def apply_mission_rewards(
    mission: MissionDefinition,
    progress: MissionProgress,
    state: MissionState,
    *,
    balance: float,
    level: int,
    xp: int,
    inventory: List[InventoryEntry],
    unlocked_pools: Set[str],
    unlocked_rods: Set[str],
    available_rods: Sequence[object],
    fish_by_name: Dict[str, "FishProfile"],
    discovered_fish: Set[str],
) -> Tuple[float, int, int, List[str]]:
    notes: List[str] = []
    rods_by_name = {getattr(rod, "name", ""): rod for rod in available_rods}

    for reward in mission.rewards:
        reward_type = reward.get("type")
        if reward_type == "money":
            amount = _safe_float(reward.get("amount"))
            if amount > 0:
                balance += amount
                progress.record_money_earned(amount)
                notes.append(f"💰 +R$ {amount:0.2f}")
        elif reward_type == "xp":
            amount = _safe_int(reward.get("amount"))
            if amount > 0:
                level, xp, level_ups = apply_xp_gain(level, xp, amount)
                notes.append(f"✨ +{amount} XP")
                if level_ups:
                    notes.append(f"⬆️ Subiu {level_ups} nível(is)!")
        elif reward_type == "fish":
            fish_name = reward.get("fish_name")
            if not isinstance(fish_name, str):
                continue
            fish_profile = fish_by_name.get(fish_name)
            if not fish_profile:
                continue
            count = max(1, _safe_int(reward.get("count", 1)))
            fixed_kg = reward.get("kg")
            for _ in range(count):
                kg = _safe_float(fixed_kg) if fixed_kg is not None else _random_kg(fish_profile)
                inventory.append(
                    InventoryEntry(
                        name=fish_profile.name,
                        rarity=fish_profile.rarity,
                        kg=kg,
                        base_value=fish_profile.base_value,
                    )
                )
            discovered_fish.add(fish_profile.name)
            notes.append(f"🎣 +{count}x {fish_profile.name}")
        elif reward_type == "unlock_rods":
            rod_names = _extract_string_list(reward.get("rod_names"))
            for rod_name in rod_names:
                if rod_name in rods_by_name:
                    unlocked_rods.add(rod_name)
                    notes.append(f"🪝 Vara desbloqueada: {rod_name}")
        elif reward_type == "unlock_pools":
            pool_names = _extract_string_list(reward.get("pool_names"))
            for pool_name in pool_names:
                unlocked_pools.add(pool_name)
                notes.append(f"🌊 Pool desbloqueada: {pool_name}")
        elif reward_type == "unlock_missions":
            mission_ids = _extract_string_list(reward.get("mission_ids"))
            for mission_id in mission_ids:
                if mission_id in state.unlocked:
                    continue
                state.unlocked.add(mission_id)
                state.unlocked_progress_baselines[mission_id] = serialize_mission_progress(progress)
                state.unlocked_completed_counts[mission_id] = len(
                    {mid for mid in state.completed if mid != mission_id}
                )
                notes.append("📜 Nova missão desbloqueada!")

    return balance, level, xp, notes


def _format_reward(reward: Dict[str, object]) -> str:
    reward_type = reward.get("type")
    if reward_type == "money":
        amount = _safe_float(reward.get("amount"))
        return f"Dinheiro: R$ {amount:0.2f}"
    if reward_type == "xp":
        amount = _safe_int(reward.get("amount"))
        return f"XP: {amount}"
    if reward_type == "fish":
        fish_name = reward.get("fish_name", "Peixe")
        count = max(1, _safe_int(reward.get("count", 1)))
        return f"Peixe: {count}x {fish_name}"
    if reward_type == "unlock_rods":
        rod_names = _extract_string_list(reward.get("rod_names"))
        return f"Desbloqueia vara(s): {', '.join(rod_names) or '-'}"
    if reward_type == "unlock_pools":
        pool_names = _extract_string_list(reward.get("pool_names"))
        return f"Desbloqueia pool(s): {', '.join(pool_names) or '-'}"
    if reward_type == "unlock_missions":
        mission_ids = _extract_string_list(reward.get("mission_ids"))
        return f"Desbloqueia missão(s): {', '.join(mission_ids) or '-'}"
    return "Recompensa desconhecida"


def _format_mission_status(mission: MissionDefinition, state: MissionState) -> str:
    if mission.mission_id not in state.unlocked:
        return "(🔒 Bloqueada)"
    if mission.mission_id in state.claimed:
        return "(✅ Recompensa resgatada)"
    if mission.mission_id in state.completed:
        return "(🎁 Recompensa disponível)"
    return "(🟡 Em progresso)"


def _build_mission_actions(
    mission: MissionDefinition,
    progress: MissionProgress,
    completed_missions: Set[str],
    *,
    baseline_progress: MissionProgress,
    completed_baseline: int,
    level: int,
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> Dict[str, List[Dict[str, object]]]:
    actions: Dict[str, List[Dict[str, object]]] = {}
    for requirement in mission.requirements:
        req_type = requirement.get("type")
        if req_type not in {
            "deliver_fish",
            "deliver_mutation",
            "deliver_fish_with_mutation",
            "spend_money",
        }:
            continue

        _, current, target, _ = _format_requirement(
            requirement,
            progress,
            completed_missions,
            mission.mission_id,
            baseline_progress=baseline_progress,
            completed_baseline=completed_baseline,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        )
        if current >= target:
            continue

        actions.setdefault(req_type, []).append(requirement)
    return actions


def _deliver_fish_for_mission(
    requirements: List[Dict[str, object]],
    inventory: List[InventoryEntry],
    progress: MissionProgress,
) -> bool:
    valid_indexes: List[int] = []
    for idx, entry in enumerate(inventory, start=1):
        if _entry_matches_delivery_requirements(entry, requirements):
            valid_indexes.append(idx)

    if not valid_indexes:
        print("Você não possui peixes válidos para esta missão.")
        return False

    print("\nPeixes que podem ser entregues:")
    for idx in valid_indexes:
        entry = inventory[idx - 1]
        mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
        print(f"{idx}. {entry.name} ({entry.kg:0.2f}kg){mutation_label}")

    selection = input("Digite o número do peixe para entregar: ").strip()
    if not selection.isdigit():
        print("Entrada inválida.")
        return False

    selected_index = int(selection)
    if selected_index not in valid_indexes:
        print("Peixe não elegível para esta missão.")
        return False

    delivered = inventory.pop(selected_index - 1)
    progress.record_fish_delivered(delivered.name, delivered.mutation_name)
    return True


def _entry_matches_delivery_requirements(
    entry: InventoryEntry,
    requirements: List[Dict[str, object]],
) -> bool:
    for requirement in requirements:
        fish_name = requirement.get("fish_name")
        mutation_name = requirement.get("mutation_name")
        req_type = requirement.get("type")

        if isinstance(fish_name, str) and entry.name != fish_name:
            continue
        if req_type == "deliver_mutation":
            if not entry.mutation_name:
                continue
            if isinstance(mutation_name, str) and entry.mutation_name != mutation_name:
                continue
        if req_type == "deliver_fish_with_mutation":
            if not entry.mutation_name:
                continue
            if isinstance(mutation_name, str) and entry.mutation_name != mutation_name:
                continue
        return True
    return False


def _request_mission_payment(
    requirements: List[Dict[str, object]],
    progress: MissionProgress,
    baseline_progress: MissionProgress,
    balance: float,
) -> float:
    required_amount = _required_spend_payment_amount(requirements, progress, baseline_progress)
    if required_amount <= 0:
        return 0.0

    print(f"Saldo atual: R$ {balance:0.2f}")
    print(f"Pagamento necessário para a missão: R$ {required_amount:0.2f}")
    if balance < required_amount:
        print("Saldo insuficiente para pagar o valor integral exigido.")
        return 0.0

    confirm = input("Confirmar pagamento integral? (s/n): ").strip().lower()
    if confirm != "s":
        print("Pagamento cancelado.")
        return 0.0
    return required_amount


def _required_spend_payment_amount(
    requirements: List[Dict[str, object]],
    progress: MissionProgress,
    baseline_progress: MissionProgress,
) -> float:
    required_amount = 0.0
    current = max(0.0, progress.total_money_spent - baseline_progress.total_money_spent)
    for requirement in requirements:
        target = _safe_float(requirement.get("amount"))
        remaining = max(0.0, target - current)
        required_amount = max(required_amount, remaining)
    return required_amount


def _format_requirement(
    requirement: Dict[str, object],
    progress: MissionProgress,
    completed_missions: Set[str],
    current_mission_id: str,
    *,
    baseline_progress: MissionProgress,
    completed_baseline: int,
    level: int,
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> Tuple[str, int, int, bool]:
    requirement_type = requirement.get("type")
    if requirement_type == "earn_money":
        target = int(_safe_float(requirement.get("amount")))
        current = max(0, int(progress.total_money_earned - baseline_progress.total_money_earned))
        return "Acumular dinheiro", current, target, current >= target
    if requirement_type == "spend_money":
        target = int(_safe_float(requirement.get("amount")))
        current = max(0, int(progress.total_money_spent - baseline_progress.total_money_spent))
        return "Pagar dinheiro", current, target, current >= target
    if requirement_type == "level":
        target = _safe_int(requirement.get("level"))
        current = level
        return "Nível", current, target, current >= target
    if requirement_type == "catch_fish":
        target = _safe_int(requirement.get("count"))
        fish_name = requirement.get("fish_name")
        if isinstance(fish_name, str):
            current = max(
                0,
                progress.fish_caught_by_name.get(fish_name, 0)
                - baseline_progress.fish_caught_by_name.get(fish_name, 0),
            )
            return f"Capturar {fish_name}", current, target, current >= target
        current = max(0, progress.fish_caught - baseline_progress.fish_caught)
        return "Capturar peixes", current, target, current >= target
    if requirement_type == "deliver_fish":
        target = _safe_int(requirement.get("count"))
        fish_name = requirement.get("fish_name")
        if isinstance(fish_name, str):
            current = max(
                0,
                progress.fish_delivered_by_name.get(fish_name, 0)
                - baseline_progress.fish_delivered_by_name.get(fish_name, 0),
            )
            return f"Entregar {fish_name}", current, target, current >= target
        current = max(0, progress.fish_delivered - baseline_progress.fish_delivered)
        return "Entregar peixes", current, target, current >= target
    if requirement_type == "sell_fish":
        target = _safe_int(requirement.get("count"))
        fish_name = requirement.get("fish_name")
        if isinstance(fish_name, str):
            current = max(
                0,
                progress.fish_sold_by_name.get(fish_name, 0)
                - baseline_progress.fish_sold_by_name.get(fish_name, 0),
            )
            return f"Vender {fish_name}", current, target, current >= target
        current = max(0, progress.fish_sold - baseline_progress.fish_sold)
        return "Vender peixes", current, target, current >= target
    if requirement_type == "catch_mutation":
        target = _safe_int(requirement.get("count"))
        mutation_name = requirement.get("mutation_name")
        if isinstance(mutation_name, str):
            current = max(
                0,
                progress.mutations_caught_by_name.get(mutation_name, 0)
                - baseline_progress.mutations_caught_by_name.get(mutation_name, 0),
            )
            return f"Capturar mutação {mutation_name}", current, target, current >= target
        current = max(0, progress.mutated_fish_caught - baseline_progress.mutated_fish_caught)
        return "Capturar mutações", current, target, current >= target
    if requirement_type == "deliver_mutation":
        target = _safe_int(requirement.get("count"))
        mutation_name = requirement.get("mutation_name")
        if isinstance(mutation_name, str):
            current = max(
                0,
                progress.mutations_delivered_by_name.get(mutation_name, 0)
                - baseline_progress.mutations_delivered_by_name.get(mutation_name, 0),
            )
            return f"Entregar mutação {mutation_name}", current, target, current >= target
        current = max(0, progress.mutated_fish_delivered - baseline_progress.mutated_fish_delivered)
        return "Entregar mutações", current, target, current >= target
    if requirement_type == "catch_fish_with_mutation":
        target = _safe_int(requirement.get("count"))
        fish_name = requirement.get("fish_name")
        if isinstance(fish_name, str):
            current = max(
                0,
                progress.fish_caught_with_mutation_by_name.get(fish_name, 0)
                - baseline_progress.fish_caught_with_mutation_by_name.get(fish_name, 0),
            )
            return f"Capturar {fish_name} com mutação", current, target, current >= target
        current = max(0, progress.mutated_fish_caught - baseline_progress.mutated_fish_caught)
        return "Capturar peixe com mutação", current, target, current >= target
    if requirement_type == "deliver_fish_with_mutation":
        target = _safe_int(requirement.get("count"))
        fish_name = requirement.get("fish_name")
        mutation_name = requirement.get("mutation_name")
        if isinstance(fish_name, str) and isinstance(mutation_name, str):
            pair_key = _fish_mutation_key(fish_name, mutation_name)
            current = max(
                0,
                progress.fish_delivered_with_mutation_pair_counts.get(pair_key, 0)
                - baseline_progress.fish_delivered_with_mutation_pair_counts.get(pair_key, 0),
            )
            return (
                f"Entregar {fish_name} com muta??o {mutation_name}",
                current,
                target,
                current >= target,
            )
        if isinstance(fish_name, str):
            current = max(
                0,
                progress.fish_delivered_with_mutation_by_name.get(fish_name, 0)
                - baseline_progress.fish_delivered_with_mutation_by_name.get(fish_name, 0),
            )
            return f"Entregar {fish_name} com muta??o", current, target, current >= target
        if isinstance(mutation_name, str):
            current = max(
                0,
                progress.mutations_delivered_by_name.get(mutation_name, 0)
                - baseline_progress.mutations_delivered_by_name.get(mutation_name, 0),
            )
            return f"Entregar muta??o {mutation_name}", current, target, current >= target
        current = max(0, progress.mutated_fish_delivered - baseline_progress.mutated_fish_delivered)
        return "Entregar peixe com muta??o", current, target, current >= target
    if requirement_type == "play_time":
        target = _safe_int(_seconds_from_requirement(requirement))
        current = max(0, int(progress.play_time_seconds - baseline_progress.play_time_seconds))
        return "Tempo de jogo (s)", current, target, current >= target
    if requirement_type == "missions_completed":
        target = _safe_int(requirement.get("count"))
        current = max(
            0,
            len({mid for mid in completed_missions if mid != current_mission_id}) - completed_baseline,
        )
        return "Missões feitas", current, target, current >= target
    if requirement_type == "bestiary_percent":
        target = _safe_int(requirement.get("percent"))
        current = int(_calculate_bestiary_percent(pools, discovered_fish))
        return "Compleção do bestiário", current, target, current >= target
    if requirement_type == "bestiary_pool_percent":
        target = _safe_int(requirement.get("percent"))
        pool_name = requirement.get("pool_name")
        current = int(_calculate_pool_percent(pools, discovered_fish, pool_name))
        label = f"Compleção da pool {pool_name}" if isinstance(pool_name, str) else "Compleção da pool"
        return label, current, target, current >= target
    return "Requisito desconhecido", 0, 0, False


def _check_requirement(
    requirement: Dict[str, object],
    progress: MissionProgress,
    completed_missions: Set[str],
    current_mission_id: str,
    *,
    baseline_progress: MissionProgress,
    completed_baseline: int,
    level: int,
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> bool:
    _, current, target, done = _format_requirement(
        requirement,
        progress,
        completed_missions,
        current_mission_id,
        baseline_progress=baseline_progress,
        completed_baseline=completed_baseline,
        level=level,
        pools=pools,
        discovered_fish=discovered_fish,
    )
    return done


def _sync_unlock_baselines(state: MissionState) -> None:
    for mission_id in state.unlocked:
        state.unlocked_progress_baselines.setdefault(mission_id, {})
        state.unlocked_completed_counts.setdefault(mission_id, 0)


def _mission_baseline_progress(state: MissionState, mission_id: str) -> MissionProgress:
    raw_baseline = state.unlocked_progress_baselines.get(mission_id, {})
    return restore_mission_progress(raw_baseline)


def _calculate_bestiary_percent(
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
) -> float:
    all_fish: Set[str] = set()
    for pool in pools:
        if not _pool_counts_for_bestiary_completion(pool):
            continue
        for fish in pool.fish_profiles:
            if _fish_counts_for_bestiary_completion(fish):
                all_fish.add(fish.name)
    if not all_fish:
        return 0.0
    discovered = sum(1 for name in all_fish if name in discovered_fish)
    return (discovered / len(all_fish)) * 100


def _calculate_pool_percent(
    pools: Sequence["FishingPool"],
    discovered_fish: Set[str],
    pool_name: Optional[object],
) -> float:
    if not isinstance(pool_name, str):
        return 0.0
    pool = next((pool for pool in pools if pool.name == pool_name), None)
    if not pool:
        return 0.0
    if not _pool_counts_for_bestiary_completion(pool):
        return 0.0
    fish_names = {
        fish.name
        for fish in pool.fish_profiles
        if _fish_counts_for_bestiary_completion(fish)
    }
    if not fish_names:
        return 0.0
    discovered = sum(1 for name in fish_names if name in discovered_fish)
    return (discovered / len(fish_names)) * 100


def _pool_counts_for_bestiary_completion(pool: "FishingPool") -> bool:
    return bool(getattr(pool, "counts_for_bestiary_completion", True))


def _fish_counts_for_bestiary_completion(fish: "FishProfile") -> bool:
    return bool(getattr(fish, "counts_for_bestiary_completion", True))


def _seconds_from_requirement(requirement: Dict[str, object]) -> float:
    if "seconds" in requirement:
        return _safe_float(requirement.get("seconds"))
    if "minutes" in requirement:
        return _safe_float(requirement.get("minutes")) * 60
    if "hours" in requirement:
        return _safe_float(requirement.get("hours")) * 3600
    return _safe_float(requirement.get("time_seconds"))


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_str_int_map(value: object) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, int] = {}
    for key, raw_val in value.items():
        if isinstance(key, str):
            result[key] = _safe_int(raw_val)
    return result


def _extract_string_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _fish_mutation_key(fish_name: str, mutation_name: str) -> str:
    return f"{fish_name}::{mutation_name}"


def _random_kg(fish: "FishProfile") -> float:
    if fish.kg_min == fish.kg_max:
        return fish.kg_min
    return random.uniform(fish.kg_min, fish.kg_max)
