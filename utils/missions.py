from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, TYPE_CHECKING

from utils.inventory import InventoryEntry
from utils.levels import apply_xp_gain
from utils.menu_input import read_menu_choice
from utils.modern_ui import MenuOption, get_ui_symbol, print_menu_panel, render_progress_bar
from utils.pagination import PAGE_NEXT_KEY, PAGE_PREV_KEY, apply_page_hotkey, get_page_slice
from utils.requirements_common import (
    collect_countable_fish_names,
    completion_percent,
    count_fish_mutation_pair,
    count_name_case_insensitive,
    fish_counts_for_bestiary_completion,
    fish_mutation_key,
    fish_name_matches,
    pool_counts_for_bestiary_completion,
    safe_float,
    safe_int,
    seconds_from_requirement,
)
from utils.ui import clear_screen

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
    total_mission_money_paid: float = 0.0
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

    def record_mission_money_paid(self, amount: float) -> None:
        if amount > 0:
            self.total_mission_money_paid += amount
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
        "total_mission_money_paid": progress.total_mission_money_paid,
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
    progress.total_mission_money_paid = _safe_float(
        raw_progress.get("total_mission_money_paid", raw_progress.get("total_money_spent"))
    )
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
    mission_page_size = 6
    current_tab = "active"
    tab_pages = {"active": 0, "history": 0}

    def _read_mission_choice(total_pages: int) -> str:
        instant_keys = {"t"}
        if total_pages > 1:
            instant_keys.update({PAGE_PREV_KEY, PAGE_NEXT_KEY})
        return read_menu_choice("> ", instant_keys=instant_keys).strip().lower()

    def _format_requirement_line(
        label: str,
        current: int,
        target: int,
        done: bool,
        *,
        dim: bool,
    ) -> str:
        status_symbol = get_ui_symbol("REQ_DONE" if done else "REQ_TODO")
        if target > 0:
            line = (
                f"{status_symbol} {label} ({current}/{target}) "
                f"{render_progress_bar(current, target)}"
            )
        else:
            line = f"{status_symbol} {label}"
        if dim:
            return f"[dim]{line}[/dim]"
        return line

    def _format_mystery_reward(reward: Dict[str, object]) -> Optional[str]:
        reward_type = reward.get("type")
        if reward_type in {"unlock_rods", "unlock_pools", "unlock_missions"}:
            return "[!] Equipamento Novo"
        return None

    def _show_mission_detail(mission: MissionDefinition, *, history_mode: bool) -> None:
        nonlocal level, xp, balance
        while True:
            update_mission_completions(
                missions,
                state,
                progress,
                level=level,
                pools=pools,
                discovered_fish=discovered_fish,
            )
            baseline_progress = _mission_baseline_progress(state, mission.mission_id)
            completed_baseline = state.unlocked_completed_counts.get(mission.mission_id, 0)

            requirement_lines: List[str] = []
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
                requirement_lines.append(
                    _format_requirement_line(
                        label,
                        current,
                        target,
                        done,
                        dim=history_mode,
                    )
                )
            if not requirement_lines:
                requirement_lines.append("[dim]- Nenhum requisito[/dim]" if history_mode else "- Nenhum requisito")

            if history_mode:
                visible_rewards = [_format_reward(reward) for reward in mission.rewards]
                reward_lines = (
                    [f"[dim]- {reward_line}[/dim]" for reward_line in visible_rewards]
                    if visible_rewards
                    else ["[dim]- Sem recompensas[/dim]"]
                )
            else:
                mystery_rewards: List[str] = []
                for reward in mission.rewards:
                    hidden_line = _format_mystery_reward(reward)
                    if hidden_line is not None:
                        mystery_rewards.append(hidden_line)
                    else:
                        mystery_rewards.append(_format_reward(reward))
                reward_lines = (
                    [f"- {reward_line}" for reward_line in mystery_rewards]
                    if mystery_rewards
                    else ["- [!] Recompensa Misteriosa"]
                )

            header_lines: List[str] = []
            if mission.description:
                if history_mode:
                    header_lines.append(f"[dim]{mission.description}[/dim]")
                else:
                    header_lines.append(mission.description)
                header_lines.append("")
            header_lines.append("Requisitos:")
            header_lines.extend(requirement_lines)
            header_lines.append("")
            header_lines.append("Recompensas:")
            header_lines.extend(reward_lines)

            options: List[MenuOption] = []
            action_map: Dict[str, str] = {}
            if not history_mode:
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
                can_claim_reward = (
                    mission.mission_id in state.completed
                    and mission.mission_id not in state.claimed
                )
                option_number = 1

                deliver_requirements = (
                    mission_actions.get("deliver_fish", [])
                    + mission_actions.get("deliver_mutation", [])
                    + mission_actions.get("deliver_fish_with_mutation", [])
                )
                if deliver_requirements:
                    key = str(option_number)
                    action_map[key] = "deliver_fish"
                    options.append(MenuOption(key, "Entregar peixe para a missão"))
                    option_number += 1
                if mission_actions.get("spend_money"):
                    key = str(option_number)
                    action_map[key] = "spend_money"
                    options.append(MenuOption(key, "Pagar dinheiro para a missão"))
                    option_number += 1
                if can_claim_reward:
                    key = str(option_number)
                    action_map[key] = "claim_reward"
                    options.append(MenuOption(key, "Resgatar recompensa"))
            options.append(MenuOption("0", "Voltar"))

            clear_screen()
            tab_label = "HISTORY" if history_mode else "ACTIVE"
            print_menu_panel(
                "MISSAO",
                breadcrumb=f"JORNADA > MISSOES > {tab_label}",
                subtitle=mission.name,
                header_lines=header_lines,
                options=options,
                prompt="Escolha uma opcao:",
                show_badge=False,
                width=90,
            )

            choice = input("> ").strip().lower()
            if choice == "0":
                return
            if history_mode:
                print("Opcao invalida.")
                input("\nEnter para voltar.")
                continue

            action = action_map.get(choice)
            if not action:
                print("Opcao invalida.")
                input("\nEnter para voltar.")
                continue

            deliver_requirements = (
                mission_actions.get("deliver_fish", [])
                + mission_actions.get("deliver_mutation", [])
                + mission_actions.get("deliver_fish_with_mutation", [])
            )
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
                    progress.record_mission_money_paid(amount)
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
                return

    while True:
        update_mission_completions(
            missions,
            state,
            progress,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
        )
        active_missions = sorted(
            (
                mission
                for mission in mission_by_id.values()
                if mission.mission_id in state.unlocked
                and mission.mission_id not in state.claimed
            ),
            key=lambda mission: mission.name,
        )
        history_missions = sorted(
            (
                mission
                for mission in mission_by_id.values()
                if mission.mission_id in state.claimed
            ),
            key=lambda mission: mission.name,
        )
        tab_missions = active_missions if current_tab == "active" else history_missions

        page_slice = get_page_slice(
            len(tab_missions),
            tab_pages[current_tab],
            mission_page_size,
        )
        tab_pages[current_tab] = page_slice.page
        paged_missions = tab_missions[page_slice.start:page_slice.end]

        clear_screen()
        options: List[MenuOption] = []
        for idx, mission in enumerate(paged_missions, start=1):
            status = _format_mission_status(mission, state)
            if current_tab == "history":
                options.append(MenuOption(str(idx), f"[dim]{mission.name} {status}[/dim]"))
            else:
                options.append(MenuOption(str(idx), f"{mission.name} {status}"))

        if page_slice.has_prev:
            options.append(MenuOption(PAGE_PREV_KEY.upper(), "Anterior"))
        if page_slice.has_next:
            options.append(MenuOption(PAGE_NEXT_KEY.upper(), "Proximo"))
        options.append(MenuOption("0", "Voltar"))

        header_lines = [
            f"Concluidas: {len(state.completed)} | Resgatadas: {len(state.claimed)}",
            f"Aba atual: {current_tab.upper()}  ([T] alternar)",
            f"Pagina {page_slice.page + 1}/{page_slice.total_pages}",
        ]
        if not paged_missions:
            if current_tab == "active":
                header_lines.append("Nenhuma missao ativa no momento.")
            else:
                header_lines.append("[dim]Nenhuma missao no historico.[/dim]")

        print_menu_panel(
            "MISSOES",
            breadcrumb="JORNADA > MISSOES",
            subtitle=current_tab.upper(),
            header_lines=header_lines,
            options=options,
            prompt="Escolha uma missao:",
            show_badge=False,
        )
        choice = _read_mission_choice(page_slice.total_pages)

        if choice == "0":
            return level, xp, balance
        if choice == "t":
            current_tab = "history" if current_tab == "active" else "active"
            continue

        next_page, moved = apply_page_hotkey(
            choice,
            tab_pages[current_tab],
            page_slice.total_pages,
        )
        if moved:
            tab_pages[current_tab] = next_page
            continue

        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        idx = int(choice)
        if not (1 <= idx <= len(paged_missions)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        selected_mission = paged_missions[idx - 1]
        _show_mission_detail(
            selected_mission,
            history_mode=current_tab == "history",
        )


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

        if isinstance(fish_name, str) and not _fish_name_matches(entry.name, fish_name):
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
    current = max(
        0.0,
        progress.total_mission_money_paid - baseline_progress.total_mission_money_paid,
    )
    for requirement in requirements:
        target = _safe_float(requirement.get("amount"))
        remaining = max(0.0, target - current)
        required_amount = max(required_amount, remaining)
    return required_amount


def _format_earn_money_requirement(
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
    target = int(_safe_float(requirement.get("amount")))
    current = max(0, int(progress.total_money_earned - baseline_progress.total_money_earned))
    return "Acumular dinheiro", current, target, current >= target


def _format_spend_money_requirement(
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
    target = int(_safe_float(requirement.get("amount")))
    current = max(
        0,
        int(progress.total_mission_money_paid - baseline_progress.total_mission_money_paid),
    )
    return "Pagar dinheiro", current, target, current >= target


def _format_level_requirement(
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
    target = _safe_int(requirement.get("level"))
    current = level
    return "Nível", current, target, current >= target


def _format_catch_fish_requirement(
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
    target = _safe_int(requirement.get("count"))
    fish_name = requirement.get("fish_name")
    if isinstance(fish_name, str):
        current = max(
            0,
            _count_fish_name(progress.fish_caught_by_name, fish_name)
            - _count_fish_name(baseline_progress.fish_caught_by_name, fish_name),
        )
        return f"Capturar {fish_name}", current, target, current >= target
    current = max(0, progress.fish_caught - baseline_progress.fish_caught)
    return "Capturar peixes", current, target, current >= target


def _format_deliver_fish_requirement(
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
    target = _safe_int(requirement.get("count"))
    fish_name = requirement.get("fish_name")
    if isinstance(fish_name, str):
        current = max(
            0,
            _count_fish_name(progress.fish_delivered_by_name, fish_name)
            - _count_fish_name(baseline_progress.fish_delivered_by_name, fish_name),
        )
        return f"Entregar {fish_name}", current, target, current >= target
    current = max(0, progress.fish_delivered - baseline_progress.fish_delivered)
    return "Entregar peixes", current, target, current >= target


def _format_sell_fish_requirement(
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
    target = _safe_int(requirement.get("count"))
    fish_name = requirement.get("fish_name")
    if isinstance(fish_name, str):
        current = max(
            0,
            _count_fish_name(progress.fish_sold_by_name, fish_name)
            - _count_fish_name(baseline_progress.fish_sold_by_name, fish_name),
        )
        return f"Vender {fish_name}", current, target, current >= target
    current = max(0, progress.fish_sold - baseline_progress.fish_sold)
    return "Vender peixes", current, target, current >= target


def _format_catch_mutation_requirement(
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


def _format_deliver_mutation_requirement(
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


def _format_catch_fish_with_mutation_requirement(
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
    target = _safe_int(requirement.get("count"))
    fish_name = requirement.get("fish_name")
    if isinstance(fish_name, str):
        current = max(
            0,
            _count_fish_name(progress.fish_caught_with_mutation_by_name, fish_name)
            - _count_fish_name(baseline_progress.fish_caught_with_mutation_by_name, fish_name),
        )
        return f"Capturar {fish_name} com mutação", current, target, current >= target
    current = max(0, progress.mutated_fish_caught - baseline_progress.mutated_fish_caught)
    return "Capturar peixe com mutação", current, target, current >= target


def _format_deliver_fish_with_mutation_requirement(
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
    target = _safe_int(requirement.get("count"))
    fish_name = requirement.get("fish_name")
    mutation_name = requirement.get("mutation_name")
    if isinstance(fish_name, str) and isinstance(mutation_name, str):
        current = max(
            0,
            _count_fish_mutation_pair(
                progress.fish_delivered_with_mutation_pair_counts,
                fish_name=fish_name,
                mutation_name=mutation_name,
            )
            - _count_fish_mutation_pair(
                baseline_progress.fish_delivered_with_mutation_pair_counts,
                fish_name=fish_name,
                mutation_name=mutation_name,
            ),
        )
        return (
            f"Entregar {fish_name} com mutação {mutation_name}",
            current,
            target,
            current >= target,
        )
    if isinstance(fish_name, str):
        current = max(
            0,
            _count_fish_name(progress.fish_delivered_with_mutation_by_name, fish_name)
            - _count_fish_name(baseline_progress.fish_delivered_with_mutation_by_name, fish_name),
        )
        return f"Entregar {fish_name} com mutação", current, target, current >= target
    if isinstance(mutation_name, str):
        current = max(
            0,
            progress.mutations_delivered_by_name.get(mutation_name, 0)
            - baseline_progress.mutations_delivered_by_name.get(mutation_name, 0),
        )
        return f"Entregar mutação {mutation_name}", current, target, current >= target
    current = max(0, progress.mutated_fish_delivered - baseline_progress.mutated_fish_delivered)
    return "Entregar peixe com mutação", current, target, current >= target


def _format_play_time_requirement(
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
    target = _safe_int(_seconds_from_requirement(requirement))
    current = max(0, int(progress.play_time_seconds - baseline_progress.play_time_seconds))
    return "Tempo de jogo (s)", current, target, current >= target


def _format_missions_completed_requirement(
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
    target = _safe_int(requirement.get("count"))
    current = max(
        0,
        len({mid for mid in completed_missions if mid != current_mission_id}) - completed_baseline,
    )
    return "Missões feitas", current, target, current >= target


def _format_bestiary_percent_requirement(
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
    target = _safe_int(requirement.get("percent"))
    current = int(_calculate_bestiary_percent(pools, discovered_fish))
    return "Compleção do bestiário", current, target, current >= target


def _format_bestiary_pool_percent_requirement(
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
    target = _safe_int(requirement.get("percent"))
    pool_name = requirement.get("pool_name")
    current = int(_calculate_pool_percent(pools, discovered_fish, pool_name))
    label = f"Compleção da pool {pool_name}" if isinstance(pool_name, str) else "Compleção da pool"
    return label, current, target, current >= target


_REQUIREMENT_FORMATTERS = {
    "earn_money": _format_earn_money_requirement,
    "spend_money": _format_spend_money_requirement,
    "level": _format_level_requirement,
    "catch_fish": _format_catch_fish_requirement,
    "deliver_fish": _format_deliver_fish_requirement,
    "sell_fish": _format_sell_fish_requirement,
    "catch_mutation": _format_catch_mutation_requirement,
    "deliver_mutation": _format_deliver_mutation_requirement,
    "catch_fish_with_mutation": _format_catch_fish_with_mutation_requirement,
    "deliver_fish_with_mutation": _format_deliver_fish_with_mutation_requirement,
    "play_time": _format_play_time_requirement,
    "missions_completed": _format_missions_completed_requirement,
    "bestiary_percent": _format_bestiary_percent_requirement,
    "bestiary_pool_percent": _format_bestiary_pool_percent_requirement,
}


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
    formatter = _REQUIREMENT_FORMATTERS.get(requirement_type)
    if formatter is None:
        return "Requisito desconhecido", 0, 0, False
    return formatter(
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
    all_fish = collect_countable_fish_names(pools)
    return completion_percent(all_fish, discovered_fish)


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
    return completion_percent(fish_names, discovered_fish)


def _pool_counts_for_bestiary_completion(pool: "FishingPool") -> bool:
    return pool_counts_for_bestiary_completion(pool)


def _fish_counts_for_bestiary_completion(fish: "FishProfile") -> bool:
    return fish_counts_for_bestiary_completion(fish)


def _seconds_from_requirement(requirement: Dict[str, object]) -> float:
    return seconds_from_requirement(requirement, clamp_non_negative=False)


def _safe_float(value: object) -> float:
    return safe_float(value)


def _safe_int(value: object) -> int:
    return safe_int(value)


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


def _fish_name_matches(actual_name: str, expected_name: str) -> bool:
    return fish_name_matches(actual_name, expected_name)


def _count_fish_name(counts: Dict[str, int], fish_name: str) -> int:
    return count_name_case_insensitive(counts, fish_name)


def _count_fish_mutation_pair(
    counts: Dict[str, int],
    *,
    fish_name: str,
    mutation_name: str,
) -> int:
    return count_fish_mutation_pair(
        counts,
        fish_name=fish_name,
        mutation_name=mutation_name,
    )


def _fish_mutation_key(fish_name: str, mutation_name: str) -> str:
    return fish_mutation_key(fish_name, mutation_name)


def _random_kg(fish: "FishProfile") -> float:
    if fish.kg_min == fish.kg_max:
        return fish.kg_min
    return random.uniform(fish.kg_min, fish.kg_max)
