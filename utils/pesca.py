import importlib
import importlib.util
import json
import math
import os
import random
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from colorama import Fore, Style
from colorama import init as colorama_init
from pynput import keyboard

from utils.baits import BaitDefinition, build_bait_lookup, load_bait_crates
from utils.bestiary import show_bestiary
from utils.bestiary_rewards import (
    BestiaryRewardDefinition,
    BestiaryRewardState,
    load_bestiary_rewards,
    restore_bestiary_reward_state,
    serialize_bestiary_reward_state,
)
from utils.cosmetics import (
    PlayerCosmeticsState,
    UI_COLOR_DEFINITIONS,
    UI_ICON_DEFINITIONS,
    create_default_cosmetics_state,
    equip_icon_color,
    equip_ui_color,
    equip_ui_icon,
    list_unlocked_ui_colors,
    list_unlocked_ui_icons,
    restore_cosmetics_state,
    unlock_ui_color,
    unlock_ui_icon,
)
from utils.dialogue import get_menu_line
from utils.inventory import InventoryEntry, render_inventory
from utils.levels import RARITY_XP, apply_xp_gain, xp_for_rarity, xp_required_for_level
from utils.menu_input import read_menu_choice
from utils.market import (
    restore_pool_market_orders,
    show_market,
)
from utils.crafting import (
    CraftingProgress,
    CraftingState,
    count_inventory_fish,
    count_inventory_mutations,
    load_crafting_definitions,
    restore_crafting_progress,
    restore_crafting_state,
    update_crafting_unlocks,
)
from utils.modern_ui import (
    MenuOption,
    print_menu_panel,
    render_fishing_hud_line,
    set_ui_cosmetics,
    use_modern_ui,
)
from utils.pagination import (
    PAGE_NEXT_KEY,
    PAGE_PREV_KEY,
    apply_page_hotkey,
    get_page_slice,
)
from utils.missions import (
    MissionDefinition,
    MissionProgress,
    MissionState,
    apply_mission_rewards,
    load_missions,
    restore_mission_progress,
    restore_mission_state,
    show_missions_menu,
    update_mission_completions,
)
from utils.mutations import (
    Mutation,
    choose_mutation,
    filter_mutations_for_rod,
    load_mutations,
    load_mutations_optional,
)
from utils.events import ActiveEvent, EventDefinition, EventManager
from utils.hunts import ActiveHunt, HuntDefinition, HuntManager
from utils.pesca_autosave import autosave_state as _autosave_state_impl
from utils.pesca_boot import (
    build_default_unlocked_pools,
    build_default_unlocked_rods,
    select_default_pool,
    select_starter_rod,
)
from utils.pesca_devtools_helpers import sorted_baits_for_dev_menu
from utils.pesca_inventory_helpers import (
    active_bait_summary as inventory_active_bait_summary,
    active_cosmetics_summary as inventory_active_cosmetics_summary,
    list_owned_baits as inventory_list_owned_baits,
    sanitize_equipped_bait as inventory_sanitize_equipped_bait,
)
from utils.pesca_round_helpers import (
    calculate_effective_rod_stats,
    combine_fish_profiles,
    filter_eligible_fish,
    resolve_active_bait,
)
from utils.rods import Rod, load_rods
from utils.save_system import (
    get_default_save_path,
    load_game,
    restore_balance,
    restore_bait_inventory,
    restore_discovered_fish,
    restore_equipped_bait,
    restore_equipped_rod,
    restore_hunt_state,
    restore_inventory,
    restore_level,
    restore_owned_rods,
    restore_selected_pool,
    restore_unlocked_pools,
    restore_xp,
)
from utils.ui import clear_screen

# -----------------------------
# Config / Modelos
# -----------------------------

VALID_KEYS = ["w", "a", "s", "d"]
PACE_WINDOW_S = 1.5
PACE_TRIGGER_CATCHES = 2
PACE_STEP_MULTIPLIER = 0.85
PACE_MIN_TIME_MULTIPLIER = 0.55


def flush_input_buffer() -> None:
    if os.name == "nt":
        if importlib.util.find_spec("msvcrt"):
            msvcrt = importlib.import_module("msvcrt")
            while msvcrt.kbhit():
                msvcrt.getch()
        return

    if importlib.util.find_spec("termios"):
        termios = importlib.import_module("termios")
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)


def _reel_time_multiplier_from_pace(recent_catch_count: int) -> float:
    if recent_catch_count < PACE_TRIGGER_CATCHES:
        return 1.0

    stacks = recent_catch_count - PACE_TRIGGER_CATCHES + 1
    multiplier = PACE_STEP_MULTIPLIER ** stacks
    return max(PACE_MIN_TIME_MULTIPLIER, multiplier)


@dataclass(frozen=True)
class FishingAttempt:
    """Descreve uma tentativa de pesca (o 'quick time event')."""
    sequence: List[str]
    time_limit_s: float  # tempo TOTAL para completar a sequência
    allowed_keys: List[str]


@dataclass
class FishingResult:
    success: bool
    reason: str
    typed: List[str]
    elapsed_s: float



class FishProfile:
    """
    Perfil de peixe: define como gerar a tentativa (sequência + tempo).
    Isso deixa a lógica expansível: cada peixe pode ter seu comportamento.
    """
    def __init__(
        self,
        name: str,
        rarity: str,
        description: str,
        kg_min: float,
        kg_max: float,
        base_value: float,
        sequence_len: Optional[int] = None,
        reaction_time_s: float = 2.5,
        sequence_len_range=(4, 8),
        allowed_keys=None,
        generator: Optional[Callable[[], FishingAttempt]] = None,
        counts_for_bestiary_completion: bool = True,
    ):
        self.name = name
        self.rarity = rarity
        self.description = description
        self.kg_min = kg_min
        self.kg_max = kg_max
        self.base_value = base_value
        self.sequence_len = sequence_len
        self.reaction_time_s = reaction_time_s
        self.sequence_len_range = sequence_len_range
        self.allowed_keys = allowed_keys or VALID_KEYS
        self.counts_for_bestiary_completion = counts_for_bestiary_completion

        # Se quiser, pode plugar um gerador customizado por peixe.
        self._custom_generator = generator

    def generate_attempt(self) -> FishingAttempt:
        if self._custom_generator:
            return self._custom_generator()

        if self.sequence_len:
            seq = [random.choice(self.allowed_keys) for _ in range(self.sequence_len)]
        else:
            length = random.randint(*self.sequence_len_range)
            seq = [random.choice(self.allowed_keys) for _ in range(length)]
        return FishingAttempt(
            sequence=seq,
            time_limit_s=self.reaction_time_s,
            allowed_keys=list(self.allowed_keys),
        )


@dataclass
class FishingPool:
    name: str
    fish_profiles: List[FishProfile]
    folder: Path
    description: str
    rarity_weights: Dict[str, int]
    unlocked_default: bool = False
    hidden_from_pool_selection: bool = False
    hidden_from_bestiary_until_unlocked: bool = False
    counts_for_bestiary_completion: bool = True
    secret_entry_code: str = ""

    def choose_fish(
        self,
        eligible_fish: List[FishProfile],
        rod_luck: float,
        rarity_weights_override: Optional[Dict[str, int]] = None,
    ) -> FishProfile:
        fish_by_rarity: Dict[str, List[FishProfile]] = {}
        for fish in eligible_fish:
            fish_by_rarity.setdefault(fish.rarity, []).append(fish)

        available_rarities = list(fish_by_rarity.keys())
        if not available_rarities:
            raise RuntimeError("Pool sem peixes disponíveis.")

        base_weights = rarity_weights_override or self.rarity_weights
        weights_by_rarity = _apply_luck_to_weights(
            {
                rarity: base_weights.get(rarity, 0)
                for rarity in available_rarities
            },
            rod_luck,
        )
        weights = [weights_by_rarity.get(rarity, 0) for rarity in available_rarities]
        if sum(weights) <= 0:
            weights = [1 for _ in available_rarities]

        selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
        return random.choice(fish_by_rarity[selected_rarity])


def _apply_luck_to_weights(
    weights: Dict[str, float],
    rod_luck: float,
) -> Dict[str, float]:
    if not weights:
        return {}

    luck = float(rod_luck)
    if luck == 0:
        return weights

    rarities = list(weights.keys())
    ordered = sorted(
        rarities,
        key=lambda rarity: RARITY_XP.get(rarity, 0),
    )
    max_rank = max(0, len(ordered) - 1)
    if max_rank == 0:
        return weights

    ranks = {rarity: index for index, rarity in enumerate(ordered)}
    total = sum(float(value) for value in weights.values())
    adjusted: Dict[str, float] = {}
    for rarity in rarities:
        rank = ranks.get(rarity, 0)
        rank_ratio = rank / max_rank
        if luck > 0:
            luck_boost = luck * (1 + luck)
            multiplier = 1 + (luck_boost * rank_ratio)
        else:
            penalty = abs(luck) * (1 + abs(luck))
            multiplier = max(0.0, 1 - (penalty * rank_ratio))
        adjusted[rarity] = float(weights[rarity]) * multiplier

    adjusted_total = sum(adjusted.values())
    if adjusted_total <= 0:
        return weights

    scale = total / adjusted_total if total > 0 else 1.0
    return {rarity: value * scale for rarity, value in adjusted.items()}


def normalize_rarity_weights(
    configured_weights: Dict[str, float],
    available_rarities: List[str],
) -> Dict[str, int]:
    filtered = {
        rarity: float(weight)
        for rarity, weight in configured_weights.items()
        if rarity in available_rarities and weight > 0
    }

    if not filtered:
        if not available_rarities:
            return {}
        even_weight = 100 // len(available_rarities)
        weights = {rarity: even_weight for rarity in available_rarities}
        remainder = 100 - sum(weights.values())
        for rarity in available_rarities[:remainder]:
            weights[rarity] += 1
        return weights

    total = sum(filtered.values())
    scaled = {rarity: (weight / total) * 100 for rarity, weight in filtered.items()}
    floors = {rarity: math.floor(value) for rarity, value in scaled.items()}
    remainder = 100 - sum(floors.values())

    fractions = sorted(
        ((rarity, scaled[rarity] - floors[rarity]) for rarity in floors),
        key=lambda item: item[1],
        reverse=True,
    )
    for rarity, _ in fractions[:remainder]:
        floors[rarity] += 1

    return floors


def combine_rarity_weights(
    base_weights: Dict[str, float],
    extra_weights: Dict[str, float],
    available_rarities: List[str],
) -> Dict[str, int]:
    combined = {
        rarity: float(base_weights.get(rarity, 0)) + float(extra_weights.get(rarity, 0))
        for rarity in available_rarities
    }
    return normalize_rarity_weights(combined, available_rarities)


def load_fish_profiles_from_dir(fish_dir: Path) -> List[FishProfile]:
    if not fish_dir.exists():
        return []

    fish_profiles: List[FishProfile] = []
    for fish_path in sorted(fish_dir.glob("*.json")):
        try:
            with fish_path.open("r", encoding="utf-8") as handle:
                fish_data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: peixe ignorado ({fish_path}): {exc}")
            continue
        if not isinstance(fish_data, dict):
            print(f"Aviso: peixe ignorado ({fish_path}): formato invalido.")
            continue

        name = fish_data.get("name")
        if not name:
            continue

        sequence_len = fish_data.get("sequence_len")
        if sequence_len is not None:
            sequence_len = int(sequence_len)

        fish_profiles.append(
            FishProfile(
                name=name,
                rarity=fish_data.get("rarity", "Desconhecida"),
                description=fish_data.get("description", ""),
                kg_min=float(fish_data.get("kg_min", 0.0)),
                kg_max=float(fish_data.get("kg_max", 0.0)),
                base_value=float(fish_data.get("base_value", 0.0)),
                sequence_len=sequence_len,
                reaction_time_s=float(fish_data.get("reaction_time_s", 2.5)),
                sequence_len_range=tuple(fish_data.get("sequence_len_range", (4, 8))),
                allowed_keys=fish_data.get("allowed_keys"),
                counts_for_bestiary_completion=not bool(
                    fish_data.get("exclude_from_bestiary_completion", False)
                ),
            )
        )

    return fish_profiles


def load_events(base_dir: Path) -> List[EventDefinition]:
    if not base_dir.exists():
        return []

    events: List[EventDefinition] = []
    for event_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        config_path = event_dir / "event.json"
        if not config_path.exists():
            continue

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: evento ignorado ({config_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: evento ignorado ({config_path}): formato invalido.")
            continue

        name = data.get("name")
        if not name:
            continue

        chance_percent = float(data.get("chance_percent", 0.0))
        interval_minutes = float(data.get("interval_minutes", 0.0))
        duration_minutes = float(data.get("duration_minutes", 0.0))
        luck_multiplier = float(data.get("luck_multiplier", 1.0))
        xp_multiplier = float(data.get("xp_multiplier", 1.0))
        rarity_weights = data.get("rarity_chances", {})
        if not isinstance(rarity_weights, dict):
            rarity_weights = {}

        fish_profiles = load_fish_profiles_from_dir(event_dir / "fish")
        mutations = load_mutations_optional(event_dir / "mutations")

        events.append(
            EventDefinition(
                name=name,
                description=data.get("description", ""),
                chance=max(0.0, chance_percent / 100),
                interval_s=max(0.0, interval_minutes * 60),
                duration_s=max(0.0, duration_minutes * 60),
                luck_multiplier=max(0.0, luck_multiplier),
                xp_multiplier=max(0.0, xp_multiplier),
                fish_profiles=fish_profiles,
                rarity_weights=rarity_weights,
                mutations=mutations,
            )
        )

    return events


def load_hunts(
    base_dir: Path,
    valid_pool_names: Optional[set[str]] = None,
) -> List[HuntDefinition]:
    if not base_dir.exists():
        return []

    hunts: List[HuntDefinition] = []
    for hunt_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        config_path = hunt_dir / f"{hunt_dir.name}.json"
        if not config_path.exists():
            json_candidates = sorted(hunt_dir.glob("*.json"))
            if len(json_candidates) != 1:
                continue
            config_path = json_candidates[0]

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: hunt ignorada ({config_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: hunt ignorada ({config_path}): formato invalido.")
            continue

        name = data.get("name")
        pool_name = data.get("pool_name")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(pool_name, str) or not pool_name:
            continue
        if valid_pool_names is not None and pool_name not in valid_pool_names:
            continue

        try:
            duration_minutes = float(data.get("duration_minutes", 0.0))
            check_interval_seconds = float(data.get("check_interval_seconds", 0.0))
            disturbance_per_catch = float(data.get("disturbance_per_catch", 0.0))
            disturbance_max = float(data.get("disturbance_max", 0.0))
            cooldown_minutes = float(data.get("cooldown_minutes", 0.0))
            disturbance_decay_per_check = float(
                data.get("disturbance_decay_per_check", 0.0)
            )
        except (TypeError, ValueError):
            continue

        disturbance_max = max(0.0, disturbance_max)
        if disturbance_max <= 0:
            continue

        rarity_weights = data.get("rarity_chances", {})
        if not isinstance(rarity_weights, dict):
            rarity_weights = {}

        fish_profiles = load_fish_profiles_from_dir(hunt_dir / "fish")
        if not fish_profiles:
            continue

        hunts.append(
            HuntDefinition(
                hunt_id=hunt_dir.name,
                name=name,
                description=data.get("description", ""),
                pool_name=pool_name,
                duration_s=max(0.0, duration_minutes * 60),
                check_interval_s=max(0.0, check_interval_seconds),
                disturbance_per_catch=max(0.0, disturbance_per_catch),
                disturbance_max=disturbance_max,
                rarity_weights=rarity_weights,
                fish_profiles=fish_profiles,
                cooldown_s=max(0.0, cooldown_minutes * 60),
                disturbance_decay_per_check=max(0.0, disturbance_decay_per_check),
            )
        )

    return hunts


def load_pools(base_dir: Path) -> List[FishingPool]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de pools não encontrado: {base_dir}")

    pools: List[FishingPool] = []
    for pool_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        config_path = pool_dir / "pool.json"
        if not config_path.exists():
            continue

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: pool ignorada ({config_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: pool ignorada ({config_path}): formato invalido.")
            continue

        fish_profiles = load_fish_profiles_from_dir(pool_dir / "fish")

        if not fish_profiles:
            continue

        available_rarities = sorted({fish.rarity for fish in fish_profiles})
        configured_weights = data.get("rarity_chances", {})
        if not isinstance(configured_weights, dict):
            configured_weights = {}
        rarity_weights = normalize_rarity_weights(configured_weights, available_rarities)
        raw_counts_flag = data.get("counts_for_bestiary_completion")
        if isinstance(raw_counts_flag, bool):
            counts_for_bestiary_completion = raw_counts_flag
        else:
            counts_for_bestiary_completion = not bool(
                data.get("exclude_from_bestiary_completion", False)
            )
        hidden_from_pool_selection = bool(data.get("hidden_from_pool_selection", False))
        hidden_from_bestiary_until_unlocked = bool(
            data.get("hidden_from_bestiary_until_unlocked", False)
        )
        raw_secret_entry_code = data.get("secret_entry_code", "")
        if isinstance(raw_secret_entry_code, str):
            secret_entry_code = raw_secret_entry_code.strip().casefold()
        else:
            secret_entry_code = ""
        if hidden_from_pool_selection and not secret_entry_code:
            secret_entry_code = pool_dir.name.strip().casefold()

        pools.append(
            FishingPool(
                name=data.get("name", pool_dir.name),
                fish_profiles=fish_profiles,
                folder=pool_dir,
                description=data.get("description", ""),
                rarity_weights=rarity_weights,
                unlocked_default=bool(data.get("unlocked_default", False)),
                hidden_from_pool_selection=hidden_from_pool_selection,
                hidden_from_bestiary_until_unlocked=hidden_from_bestiary_until_unlocked,
                counts_for_bestiary_completion=counts_for_bestiary_completion,
                secret_entry_code=secret_entry_code,
            )
        )

    if not pools:
        raise RuntimeError("Nenhuma pool encontrada. Verifique os arquivos em /pools.")

    return pools


def select_pool(pools: List[FishingPool], unlocked_pools: set[str]) -> FishingPool:
    available_pools = [
        pool
        for pool in pools
        if pool.name in unlocked_pools and not pool.hidden_from_pool_selection
    ]
    secret_pools_by_code = {
        pool.secret_entry_code: pool
        for pool in pools
        if pool.secret_entry_code
    }

    if use_modern_ui():
        if not available_pools and not secret_pools_by_code:
            raise RuntimeError("Nenhuma pool desbloqueada.")

        while True:
            clear_screen()
            header_lines = [f"Disponiveis: {len(available_pools)}"]
            print_menu_panel(
                "POOLS",
                subtitle="Escolha onde pescar",
                header_lines=header_lines,
                options=[
                    MenuOption(str(idx), pool.name, "Desbloqueada")
                    for idx, pool in enumerate(available_pools, start=1)
                ],
                prompt="Digite o numero da pool:",
                show_badge=False,
            )
            choice = input("> ").strip()
            if not choice:
                print("Entrada invalida. Digite apenas o numero da pool.")
                continue

            secret_pool = secret_pools_by_code.get(choice.casefold())
            if secret_pool:
                unlocked_pools.add(secret_pool.name)
                return secret_pool

            if not choice.isdigit():
                print("Entrada invalida. Digite apenas o numero da pool.")
                continue

            idx = int(choice)
            if 1 <= idx <= len(available_pools):
                return available_pools[idx - 1]

            print("Numero fora do intervalo. Tente novamente.")

    print("Escolha uma pool para pescar:")
    for idx, pool in enumerate(available_pools, start=1):
        print(f"{idx}. {pool.name}")
    if not available_pools and not secret_pools_by_code:
        raise RuntimeError("Nenhuma pool desbloqueada.")

    while True:
        choice = input("Digite o numero da pool: ").strip()
        if not choice:
            print("Entrada invalida. Digite apenas o numero da pool.")
            continue

        secret_pool = secret_pools_by_code.get(choice.casefold())
        if secret_pool:
            unlocked_pools.add(secret_pool.name)
            return secret_pool

        if not choice.isdigit():
            print("Entrada invalida. Digite apenas o numero da pool.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(available_pools):
            return available_pools[idx - 1]

        print("Numero fora do intervalo. Tente novamente.")


# -----------------------------
# Engine de Input (sem Enter)
# -----------------------------

class KeyStream:
    """
    Captura teclas em tempo real e fornece os eventos para o jogo.
    Implementado com pynput (cross-platform).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._buffer: List[str] = []
        self._stop = False
        self._listener: Optional[keyboard.Listener] = None

    def start(self):
        def on_press(key):
            # Tenta capturar letras; ignora o resto
            try:
                ch = key.char
            except AttributeError:
                ch = None

            if ch:
                ch = ch.lower()
                with self._lock:
                    self._buffer.append(ch)

            # ESC encerra o jogo
            if key == keyboard.Key.esc:
                self._stop = True
                return False  # para o listener

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def stop_requested(self) -> bool:
        return self._stop

    def pop_all(self) -> List[str]:
        with self._lock:
            items = self._buffer[:]
            self._buffer.clear()
        return items


# -----------------------------
# Lógica da Pesca (flexível)
# -----------------------------

class FishingMiniGame:
    """
    Controla uma tentativa (um peixe).
    Mantém estado mínimo e retorna um FishingResult no final.
    """
    def __init__(
        self,
        attempt: FishingAttempt,
        *,
        can_slash: bool = False,
        slash_chance: float = 0.0,
        slash_power: int = 1,
        can_slam: bool = False,
        slam_chance: float = 0.0,
        slam_time_bonus: float = 0.0,
    ):
        self.attempt = attempt
        self.typed: List[str] = []
        self.index = 0
        self.start_time = 0.0
        self.can_slash = can_slash
        self.slash_chance = max(0.0, min(1.0, float(slash_chance)))
        self.slash_power = max(1, int(slash_power))
        self.can_slam = can_slam
        self.slam_chance = max(0.0, min(1.0, float(slam_chance)))
        self.slam_time_bonus = max(0.0, float(slam_time_bonus))
        self.bonus_time_s = 0.0

    def expected_key(self) -> Optional[str]:
        if self.index >= len(self.attempt.sequence):
            return None
        return self.attempt.sequence[self.index]

    def is_done(self) -> bool:
        return self.index >= len(self.attempt.sequence)

    def total_time_limit(self) -> float:
        return self.attempt.time_limit_s + self.bonus_time_s

    def time_left(self) -> float:
        elapsed = time.perf_counter() - self.start_time
        return max(0.0, self.total_time_limit() - elapsed)

    def begin(self):
        self.start_time = time.perf_counter()

    def handle_key(self, key: str) -> Optional[FishingResult]:
        """
        Processa uma tecla. Retorna FishingResult se terminou (sucesso/erro),
        ou None se ainda está em andamento.
        """
        # só considera teclas permitidas
        if key not in self.attempt.allowed_keys:
            return None

        # timeout
        elapsed = time.perf_counter() - self.start_time
        if elapsed > self.total_time_limit():
            return FishingResult(False, "Tempo esgotado", self.typed[:], elapsed)

        min_slash_index = self.index + 2
        if self.can_slash and self.slash_chance > 0 and min_slash_index < len(self.attempt.sequence):
            if random.random() <= self.slash_chance:
                remaining_letters = len(self.attempt.sequence) - self.index
                if self.slash_power > remaining_letters:
                    self.index = len(self.attempt.sequence)
                    elapsed = time.perf_counter() - self.start_time
                    return FishingResult(True, "Capturou o peixe!", self.typed[:], elapsed)

                removable = len(self.attempt.sequence) - min_slash_index
                cuts = min(self.slash_power, removable)
                for _ in range(cuts):
                    remove_index = random.randrange(min_slash_index, len(self.attempt.sequence))
                    self.attempt.sequence.pop(remove_index)
                if self.is_done():
                    elapsed = time.perf_counter() - self.start_time
                    return FishingResult(True, "Capturou o peixe!", self.typed[:], elapsed)

        if self.can_slam and self.slam_chance > 0 and self.slam_time_bonus > 0:
            if random.random() <= self.slam_chance:
                self.bonus_time_s += self.slam_time_bonus

        expected = self.expected_key()
        if expected is None:
            # já terminou, ignora
            return None

        self.typed.append(key)

        if key == expected:
            self.index += 1
            if self.is_done():
                elapsed = time.perf_counter() - self.start_time
                return FishingResult(True, "Capturou o peixe!", self.typed[:], elapsed)
            return None

        # errou tecla
        elapsed = time.perf_counter() - self.start_time
        return FishingResult(False, f"Errou (esperado '{expected}', veio '{key}')", self.typed[:], elapsed)

    def check_timeout(self) -> Optional[FishingResult]:
        elapsed = time.perf_counter() - self.start_time
        if elapsed > self.total_time_limit() and not self.is_done():
            return FishingResult(False, "Tempo esgotado", self.typed[:], elapsed)
        return None


# -----------------------------
# UI simples de terminal
# -----------------------------

def render(
    attempt: FishingAttempt,
    typed: List[str],
    time_left: float,
    total_time_s: Optional[float] = None,
):
    def _terminal_line_width(default: int = 80) -> int:
        try:
            columns = os.get_terminal_size().columns
        except OSError:
            columns = default
        # Keep one column free to avoid hard-wrap in narrow terminals.
        return max(20, columns - 1)

    def _trim_line(line: str, limit: int) -> str:
        if len(line) <= limit:
            return line
        if limit <= 3:
            return line[:limit]
        return f"{line[:limit - 3]}..."

    line_width = _terminal_line_width()

    if use_modern_ui():
        if line_width >= 96:
            line = render_fishing_hud_line(
                attempt,
                typed,
                time_left,
                total_time_s=total_time_s,
            ).lstrip("\r")
        else:
            remaining = attempt.sequence[len(typed):]
            seq_str = " ".join(k.upper() for k in remaining) if remaining else "OK"
            seq_str = _trim_line(seq_str, max(6, line_width - 34))
            line = (
                f"HUD | Seq: {seq_str} | {time_left:0.2f}s | "
                f"{len(typed)}/{len(attempt.sequence)} | ESC"
            )

        line = _trim_line(line, line_width)
        # Redraw a single line without printing filler spaces each frame.
        print(f"\r\033[2K{line}", end="", flush=True)
        return

    seq = attempt.sequence
    idx = len(typed)

    # Mostra apenas as teclas restantes
    remaining = seq[idx:]
    seq_str = " ".join(k.upper() for k in remaining) if remaining else "✔"

    # Barra de tempo
    total = max(0.001, total_time_s if total_time_s is not None else attempt.time_limit_s)
    ratio = max(0.0, min(1.0, time_left / total))
    bar_len = 20
    filled = int(bar_len * ratio)
    bar = "▮" * filled + " " * (bar_len - filled)

    line = (
        f"Seq: {seq_str:<15} "
        f"Tempo: [{bar}] {time_left:0.2f}s   (ESC sai)"
    )
    line = _trim_line(line, line_width)
    print(f"\r\033[2K{line}", end="", flush=True)

def show_main_menu(
    selected_pool: FishingPool,
    balance: float,
    level: int,
    xp: int,
    active_event: Optional[ActiveEvent],
    active_hunt: Optional[ActiveHunt],
    dev_mode: bool = False,
) -> str:
    if use_modern_ui():
        clear_screen()
        header_lines = [
            get_menu_line(),
            f"Pool: {selected_pool.name}",
            f"Saldo: ${balance:0.2f}",
            f"Nivel: {level} | XP: {xp}/{xp_required_for_level(level)}",
        ]
        if dev_mode:
            header_lines.append("Modo dev ativo")
        if active_event:
            time_left = math.ceil(active_event.time_left() / 60)
            event = active_event.definition
            header_lines.append(
                f"Evento ativo: {event.name} ({time_left} min restantes)"
            )
            if event.description:
                header_lines.append(f"  {event.description}")
            header_lines.append(
                f"  Sorte x{event.luck_multiplier:0.2f} | "
                f"XP x{event.xp_multiplier:0.2f}"
            )
        if active_hunt:
            time_left = math.ceil(active_hunt.time_left() / 60)
            hunt = active_hunt.definition
            header_lines.append(
                f"Hunt ativa: {hunt.name} ({time_left} min restantes)"
            )
            if hunt.description:
                header_lines.append(f"  {hunt.description}")

        options = [
            MenuOption("1", "Pescar", "Iniciar rodada"),
            MenuOption("2", "Pools", "Trocar local"),
            MenuOption("3", "Inventario", "Peixes e vara"),
            MenuOption("4", "Mercado", "Vender / comprar"),
            MenuOption("5", "Bestiario", "Descobertas"),
            MenuOption("6", "Missoes", "Progresso"),
        ]
        if dev_mode:
            options.append(MenuOption("7", "Dev Tools", "Editar save"))
        options.append(MenuOption("0", "Sair", "Salvar e sair"))

        print_menu_panel(
            "FISCHING OVERHAUL",
            subtitle="Main Menu",
            header_lines=header_lines,
            options=options,
            prompt="Escolha uma opcao:",
        )
        return input("> ").strip()

    clear_screen()
    print("=== Menu Principal ===")
    print(get_menu_line())
    print(f"Pool atual: {selected_pool.name}")
    print(f"Saldo: ${balance:0.2f}")
    print(f"Nivel: {level} | XP: {xp}/{xp_required_for_level(level)}")
    if dev_mode:
        print("Modo dev ativo")
    if active_event:
        time_left = math.ceil(active_event.time_left() / 60)
        event = active_event.definition
        print(
            f"Evento ativo: {event.name} "
            f"({time_left} min restantes)"
        )
        if event.description:
            print(f"   {event.description}")
        print(
            "   "
            f"Sorte x{event.luck_multiplier:0.2f} | "
            f"XP x{event.xp_multiplier:0.2f}"
        )
    if active_hunt:
        time_left = math.ceil(active_hunt.time_left() / 60)
        hunt = active_hunt.definition
        print(
            f"Hunt ativa: {hunt.name} "
            f"({time_left} min restantes)"
        )
        if hunt.description:
            print(f"   {hunt.description}")
    print("1. Pescar")
    print("2. Pools")
    print("3. Inventario")
    print("4. Mercado")
    print("5. Bestiario")
    print("6. Missoes")
    if dev_mode:
        print("7. Dev Tools")
    print("0. Sair")
    return input("Escolha uma opcao: ").strip()


def show_dev_save_editor(
    *,
    balance: float,
    level: int,
    xp: int,
    selected_pool: FishingPool,
    equipped_rod: Rod,
    pools: List[FishingPool],
    available_rods: List[Rod],
    owned_rods: List[Rod],
    unlocked_pools: set[str],
    unlocked_rods: set[str],
    discovered_fish: set[str],
    inventory: List[InventoryEntry],
    bait_by_id: Dict[str, BaitDefinition],
    bait_inventory: Dict[str, int],
    equipped_bait_id: Optional[str],
    fish_by_name: Dict[str, FishProfile],
    available_mutations: List[Mutation],
    missions: List[MissionDefinition],
    mission_state: MissionState,
    mission_progress: MissionProgress,
    event_manager: EventManager,
    hunt_manager: HuntManager,
) -> tuple[float, int, int, FishingPool, Rod, Optional[str]]:
    while True:
        if equipped_bait_id and (
            equipped_bait_id not in bait_by_id
            or bait_inventory.get(equipped_bait_id, 0) <= 0
        ):
            equipped_bait_id = None
        equipped_bait_name = (
            bait_by_id[equipped_bait_id].name
            if equipped_bait_id and equipped_bait_id in bait_by_id
            else "Nenhuma"
        )
        total_bait_units = sum(quantity for quantity in bait_inventory.values() if quantity > 0)

        if use_modern_ui():
            clear_screen()
            print_menu_panel(
                "DEV TOOLS",
                subtitle="Editor de save",
                header_lines=[
                    f"Saldo: ${balance:0.2f}",
                    f"Nivel: {level} | XP: {xp}/{xp_required_for_level(level)}",
                    f"Pools desbloqueadas: {len(unlocked_pools)}/{len(pools)}",
                    f"Varas desbloqueadas: {len(unlocked_rods)}/{len(available_rods)}",
                    f"Vara equipada: {equipped_rod.name}",
                    f"Isca equipada: {equipped_bait_name}",
                    f"Unidades de isca: {total_bait_units}",
                    f"Pool atual: {selected_pool.name}",
                ],
                options=[
                    MenuOption("1", "Set saldo", "Define saldo manualmente"),
                    MenuOption("2", "Set nivel", "Define nivel"),
                    MenuOption("3", "Set XP", "Define XP atual"),
                    MenuOption("4", "Unlock pools", "Desbloqueia todas as pools"),
                    MenuOption("5", "Unlock pool", "Desbloqueia uma pool"),
                    MenuOption("6", "Unlock rods", "Desbloqueia e adiciona todas"),
                    MenuOption("7", "Unlock rod", "Desbloqueia e adiciona uma"),
                    MenuOption("8", "Equip rod", "Troca vara equipada"),
                    MenuOption("9", "Discover fish", "Marca todos os peixes"),
                    MenuOption("10", "Set pool", "Troca pool atual"),
                    MenuOption("11", "Complete missions", "Conclui e resgata todas"),
                    MenuOption("12", "Add fish", "Adiciona peixe no inventario"),
                    MenuOption("13", "Add fish + mutation", "Adiciona peixe com mutacao"),
                    MenuOption("14", "Force hunt", "Inicia uma hunt manualmente"),
                    MenuOption("15", "Force event", "Inicia um evento manualmente"),
                    MenuOption("16", "Add bait", "Adiciona isca ao inventario"),
                    MenuOption("0", "Voltar", "Retorna ao menu principal"),
                ],
                prompt="Escolha uma opcao:",
            )
            choice = input("> ").strip()
        else:
            clear_screen()
            print("=== Dev Tools: Editor de save ===")
            print(f"Saldo: ${balance:0.2f}")
            print(f"Nivel: {level} | XP: {xp}/{xp_required_for_level(level)}")
            print(f"Pools desbloqueadas: {len(unlocked_pools)}/{len(pools)}")
            print(f"Varas desbloqueadas: {len(unlocked_rods)}/{len(available_rods)}")
            print(f"Vara equipada: {equipped_rod.name}")
            print(f"Isca equipada: {equipped_bait_name}")
            print(f"Unidades de isca: {total_bait_units}")
            print(f"Pool atual: {selected_pool.name}")
            print("\n1. Set saldo")
            print("2. Set nivel")
            print("3. Set XP")
            print("4. Unlock pools")
            print("5. Unlock pool")
            print("6. Unlock rods")
            print("7. Unlock rod")
            print("8. Equip rod")
            print("9. Discover fish")
            print("10. Set pool")
            print("11. Complete missions")
            print("12. Add fish")
            print("13. Add fish + mutation")
            print("14. Force hunt")
            print("15. Force event")
            print("16. Add bait")
            print("0. Voltar")
            choice = input("Escolha uma opcao: ").strip()

        if choice == "0":
            return balance, level, xp, selected_pool, equipped_rod, equipped_bait_id

        if choice == "1":
            raw_value = input("Novo saldo: ").strip().replace(",", ".")
            try:
                balance = max(0.0, float(raw_value))
                print(f"Saldo atualizado para ${balance:0.2f}.")
            except ValueError:
                print("Valor invalido.")
            time.sleep(1)
            continue

        if choice == "2":
            raw_value = input("Novo nivel: ").strip()
            try:
                level = max(1, int(raw_value))
                print(f"Nivel atualizado para {level}.")
            except ValueError:
                print("Valor invalido.")
            time.sleep(1)
            continue

        if choice == "3":
            raw_value = input("Novo XP atual: ").strip()
            try:
                xp = max(0, int(raw_value))
                print(f"XP atualizado para {xp}.")
            except ValueError:
                print("Valor invalido.")
            time.sleep(1)
            continue

        if choice == "4":
            unlocked_pools.update(pool.name for pool in pools)
            print("Todas as pools foram desbloqueadas.")
            time.sleep(1)
            continue

        if choice == "5":
            clear_screen()
            print("=== Unlock pool ===")
            for index, pool in enumerate(pools, start=1):
                status = "desbloqueada" if pool.name in unlocked_pools else "bloqueada"
                print(f"{index}. {pool.name} ({status})")
            selected = input("Escolha o numero da pool (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(pools)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            pool = pools[selected_index - 1]
            unlocked_pools.add(pool.name)
            print(f"Pool desbloqueada: {pool.name}.")
            time.sleep(1)
            continue

        if choice == "6":
            owned_names = {rod.name for rod in owned_rods}
            added = 0
            for rod in available_rods:
                unlocked_rods.add(rod.name)
                if rod.name not in owned_names:
                    owned_rods.append(rod)
                    owned_names.add(rod.name)
                    added += 1
            print(f"Varas desbloqueadas. {added} adicionada(s) ao inventario.")
            time.sleep(1)
            continue

        if choice == "7":
            clear_screen()
            print("=== Unlock rod ===")
            owned_names = {rod.name for rod in owned_rods}
            for index, rod in enumerate(available_rods, start=1):
                unlocked = "U" if rod.name in unlocked_rods else "-"
                owned = "O" if rod.name in owned_names else "-"
                print(f"{index}. [{unlocked}{owned}] {rod.name}")
            selected = input("Escolha o numero da vara (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(available_rods)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            rod = available_rods[selected_index - 1]
            unlocked_rods.add(rod.name)
            if rod.name not in owned_names:
                owned_rods.append(rod)
            print(f"Vara disponivel: {rod.name}.")
            time.sleep(1)
            continue

        if choice == "8":
            clear_screen()
            print("=== Equip rod ===")
            for index, rod in enumerate(owned_rods, start=1):
                marker = " (equipada)" if rod.name == equipped_rod.name else ""
                print(f"{index}. {rod.name}{marker}")
            selected = input("Escolha o numero da vara (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(owned_rods)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            equipped_rod = owned_rods[selected_index - 1]
            unlocked_rods.add(equipped_rod.name)
            print(f"Vara equipada: {equipped_rod.name}.")
            time.sleep(1)
            continue

        if choice == "9":
            all_fish_names = {
                fish.name
                for pool in pools
                for fish in pool.fish_profiles
            }
            before = len(discovered_fish)
            discovered_fish.update(all_fish_names)
            added = len(discovered_fish) - before
            print(f"Peixes marcados no bestiario: +{added}.")
            time.sleep(1)
            continue

        if choice == "10":
            clear_screen()
            unlocked_pool_list = [pool for pool in pools if pool.name in unlocked_pools]
            if not unlocked_pool_list:
                print("Nenhuma pool desbloqueada.")
                time.sleep(1)
                continue
            print("=== Set pool ===")
            for index, pool in enumerate(unlocked_pool_list, start=1):
                marker = " (atual)" if pool.name == selected_pool.name else ""
                print(f"{index}. {pool.name}{marker}")
            selected = input("Escolha o numero da pool (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(unlocked_pool_list)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            selected_pool = unlocked_pool_list[selected_index - 1]
            print(f"Pool atual definida para: {selected_pool.name}.")
            time.sleep(1)
            continue

        if choice == "11":
            processed_missions: set[str] = set()
            claimed_count = 0
            completed_count = 0

            while True:
                pending = [
                    mission
                    for mission in missions
                    if mission.mission_id in mission_state.unlocked
                    and mission.mission_id not in mission_state.claimed
                    and mission.mission_id not in processed_missions
                ]
                if not pending:
                    break

                for mission in pending:
                    processed_missions.add(mission.mission_id)
                    if mission.mission_id not in mission_state.completed:
                        mission_state.completed.add(mission.mission_id)
                        completed_count += 1

                    balance, level, xp, _ = apply_mission_rewards(
                        mission,
                        mission_progress,
                        mission_state,
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
                    mission_state.claimed.add(mission.mission_id)
                    claimed_count += 1

            if claimed_count == 0:
                print("Nenhuma missao disponivel para completar.")
            else:
                print(
                    f"Missoes processadas: {claimed_count} | "
                    f"Marcadas como concluidas: {completed_count}."
                )
            time.sleep(1)
            continue

        if choice == "12":
            if not fish_by_name:
                print("Nao ha peixes carregados.")
                time.sleep(1)
                continue

            query = input("Nome (ou parte) do peixe: ").strip()
            if not query:
                continue

            matches = sorted(
                (
                    fish
                    for fish in fish_by_name.values()
                    if query.casefold() in fish.name.casefold()
                ),
                key=lambda fish: fish.name,
            )
            if not matches:
                print("Nenhum peixe encontrado para o filtro informado.")
                time.sleep(1)
                continue

            selected_fish: Optional[FishProfile] = None
            if len(matches) == 1:
                selected_fish = matches[0]
            else:
                clear_screen()
                print("=== Add fish ===")
                for index, fish in enumerate(matches, start=1):
                    print(f"{index}. {fish.name} [{fish.rarity}]")
                selected = input("Escolha o numero do peixe (Enter cancela): ").strip()
                if not selected:
                    continue
                try:
                    selected_index = int(selected)
                except ValueError:
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                if not (1 <= selected_index <= len(matches)):
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                selected_fish = matches[selected_index - 1]

            raw_count = input("Quantidade (padrao 1): ").strip()
            if raw_count:
                try:
                    count = max(1, int(raw_count))
                except ValueError:
                    print("Quantidade invalida.")
                    time.sleep(1)
                    continue
            else:
                count = 1

            raw_kg = input("Peso em KG (vazio = aleatorio): ").strip().replace(",", ".")
            fixed_kg: Optional[float] = None
            if raw_kg:
                try:
                    fixed_kg = max(0.01, float(raw_kg))
                except ValueError:
                    print("Peso invalido.")
                    time.sleep(1)
                    continue

            for _ in range(count):
                kg = (
                    fixed_kg
                    if fixed_kg is not None
                    else random.uniform(selected_fish.kg_min, selected_fish.kg_max)
                )
                inventory.append(
                    InventoryEntry(
                        name=selected_fish.name,
                        rarity=selected_fish.rarity,
                        kg=kg,
                        base_value=selected_fish.base_value,
                    )
                )
            discovered_fish.add(selected_fish.name)
            print(f"Adicionado(s): {count}x {selected_fish.name}.")
            time.sleep(1)
            continue

        if choice == "13":
            if not fish_by_name:
                print("Nao ha peixes carregados.")
                time.sleep(1)
                continue
            if not available_mutations:
                print("Nao ha mutacoes carregadas.")
                time.sleep(1)
                continue

            fish_query = input("Nome (ou parte) do peixe: ").strip()
            if not fish_query:
                continue

            fish_matches = sorted(
                (
                    fish
                    for fish in fish_by_name.values()
                    if fish_query.casefold() in fish.name.casefold()
                ),
                key=lambda fish: fish.name,
            )
            if not fish_matches:
                print("Nenhum peixe encontrado para o filtro informado.")
                time.sleep(1)
                continue

            selected_fish: Optional[FishProfile] = None
            if len(fish_matches) == 1:
                selected_fish = fish_matches[0]
            else:
                clear_screen()
                print("=== Add fish + mutation ===")
                for index, fish in enumerate(fish_matches, start=1):
                    print(f"{index}. {fish.name} [{fish.rarity}]")
                selected = input("Escolha o numero do peixe (Enter cancela): ").strip()
                if not selected:
                    continue
                try:
                    selected_index = int(selected)
                except ValueError:
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                if not (1 <= selected_index <= len(fish_matches)):
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                selected_fish = fish_matches[selected_index - 1]

            mutation_query = input("Nome (ou parte) da mutacao: ").strip()
            mutation_matches = sorted(
                (
                    mutation
                    for mutation in available_mutations
                    if not mutation_query
                    or mutation_query.casefold() in mutation.name.casefold()
                ),
                key=lambda mutation: mutation.name,
            )
            if not mutation_matches:
                print("Nenhuma mutacao encontrada para o filtro informado.")
                time.sleep(1)
                continue

            selected_mutation: Optional[Mutation] = None
            if len(mutation_matches) == 1:
                selected_mutation = mutation_matches[0]
            else:
                clear_screen()
                print("=== Escolher mutacao ===")
                for index, mutation in enumerate(mutation_matches, start=1):
                    print(
                        f"{index}. {mutation.name} "
                        f"(XP x{mutation.xp_multiplier:0.2f} | "
                        f"Gold x{mutation.gold_multiplier:0.2f})"
                    )
                selected = input("Escolha o numero da mutacao (Enter cancela): ").strip()
                if not selected:
                    continue
                try:
                    selected_index = int(selected)
                except ValueError:
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                if not (1 <= selected_index <= len(mutation_matches)):
                    print("Opcao invalida.")
                    time.sleep(1)
                    continue
                selected_mutation = mutation_matches[selected_index - 1]

            raw_count = input("Quantidade (padrao 1): ").strip()
            if raw_count:
                try:
                    count = max(1, int(raw_count))
                except ValueError:
                    print("Quantidade invalida.")
                    time.sleep(1)
                    continue
            else:
                count = 1

            raw_kg = input("Peso em KG (vazio = aleatorio): ").strip().replace(",", ".")
            fixed_kg: Optional[float] = None
            if raw_kg:
                try:
                    fixed_kg = max(0.01, float(raw_kg))
                except ValueError:
                    print("Peso invalido.")
                    time.sleep(1)
                    continue

            for _ in range(count):
                kg = (
                    fixed_kg
                    if fixed_kg is not None
                    else random.uniform(selected_fish.kg_min, selected_fish.kg_max)
                )
                inventory.append(
                    InventoryEntry(
                        name=selected_fish.name,
                        rarity=selected_fish.rarity,
                        kg=kg,
                        base_value=selected_fish.base_value,
                        mutation_name=selected_mutation.name,
                        mutation_xp_multiplier=selected_mutation.xp_multiplier,
                        mutation_gold_multiplier=selected_mutation.gold_multiplier,
                    )
                )
            discovered_fish.add(selected_fish.name)
            print(
                f"Adicionado(s): {count}x {selected_fish.name} "
                f"com mutacao {selected_mutation.name}."
            )
            time.sleep(1)
            continue

        if choice == "14":
            hunt_options = hunt_manager.list_hunts()
            if not hunt_options:
                print("Nao ha hunts carregadas.")
                time.sleep(1)
                continue

            clear_screen()
            print("=== Force hunt ===")
            for index, hunt in enumerate(hunt_options, start=1):
                print(f"{index}. {hunt.name} [{hunt.pool_name}]")
            selected = input("Escolha o numero da hunt (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(hunt_options)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            selected_hunt = hunt_options[selected_index - 1]
            forced = hunt_manager.force_hunt(selected_hunt.hunt_id)
            if not forced:
                print("Falha ao iniciar hunt.")
            else:
                print(f"Hunt forcada: {forced.name} em {forced.pool_name}.")
            time.sleep(1)
            continue

        if choice == "15":
            event_options = event_manager.list_events()
            if not event_options:
                print("Nao ha eventos carregados.")
                time.sleep(1)
                continue

            clear_screen()
            print("=== Force event ===")
            for index, event in enumerate(event_options, start=1):
                print(f"{index}. {event.name}")
            selected = input("Escolha o numero do evento (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(event_options)):
                print("Opcao invalida.")
                time.sleep(1)
                continue
            selected_event = event_options[selected_index - 1]
            forced = event_manager.force_event(selected_event.name)
            if not forced:
                print("Falha ao iniciar evento.")
            else:
                print(f"Evento forcado: {forced.name}.")
            time.sleep(1)
            continue

        if choice == "16":
            bait_rows = sorted_baits_for_dev_menu(
                bait_by_id,
                bait_inventory,
                equipped_bait_id,
            )
            if not bait_rows:
                print("Nao ha iscas carregadas.")
                time.sleep(1)
                continue

            clear_screen()
            print("=== Add bait ===")
            for index, (bait, quantity, is_equipped) in enumerate(bait_rows, start=1):
                marker = " (equipada)" if is_equipped else ""
                print(
                    f"{index}. [{bait.rarity}] {bait.name} x{quantity}{marker} "
                    f"- {format_bait_stats(bait)}"
                )
            selected = input("Escolha o numero da isca (Enter cancela): ").strip()
            if not selected:
                continue
            try:
                selected_index = int(selected)
            except ValueError:
                print("Opcao invalida.")
                time.sleep(1)
                continue
            if not (1 <= selected_index <= len(bait_rows)):
                print("Opcao invalida.")
                time.sleep(1)
                continue

            selected_bait = bait_rows[selected_index - 1][0]
            raw_quantity = input("Quantidade para adicionar (padrao 1): ").strip()
            if raw_quantity:
                try:
                    quantity_to_add = max(1, int(raw_quantity))
                except ValueError:
                    print("Quantidade invalida.")
                    time.sleep(1)
                    continue
            else:
                quantity_to_add = 1

            bait_inventory[selected_bait.bait_id] = (
                bait_inventory.get(selected_bait.bait_id, 0) + quantity_to_add
            )
            equip_now = input("Equipar essa isca agora? (s/n): ").strip().lower()
            if equip_now == "s":
                equipped_bait_id = selected_bait.bait_id
            print(f"Isca adicionada: {quantity_to_add}x {selected_bait.name}.")
            time.sleep(1)
            continue

        print("Opcao invalida.")
        time.sleep(1)


def autosave_state(
    save_path: Path,
    balance: float,
    inventory: List[InventoryEntry],
    bait_inventory: Dict[str, int],
    owned_rods: List[Rod],
    equipped_rod: Rod,
    equipped_bait_id: Optional[str],
    selected_pool: FishingPool,
    unlocked_pools: set[str],
    unlocked_rods: set[str],
    level: int,
    xp: int,
    discovered_fish: set[str],
    mission_state,
    mission_progress: MissionProgress,
    crafting_state: CraftingState,
    crafting_progress: CraftingProgress,
    pool_market_orders,
    bestiary_reward_state: BestiaryRewardState,
    cosmetics_state: PlayerCosmeticsState,
    hunt_manager: Optional[HuntManager],
) -> None:
    _autosave_state_impl(
        save_path,
        balance,
        inventory,
        bait_inventory,
        owned_rods,
        equipped_rod,
        equipped_bait_id,
        selected_pool,
        unlocked_pools,
        unlocked_rods,
        level,
        xp,
        discovered_fish,
        mission_state,
        mission_progress,
        crafting_state,
        crafting_progress,
        pool_market_orders,
        bestiary_reward_state,
        cosmetics_state,
        hunt_manager,
        serialize_bestiary_reward_state,
    )


def format_rod_stats(rod: Rod) -> str:
    return (
        f"Sorte: {rod.luck:.0%} | KGMax: {rod.kg_max:g} | "
        f"Controle: {rod.control:+.1f}s"
    )


def format_bait_stats(bait: BaitDefinition) -> str:
    return (
        f"Sorte: {bait.luck:+.0%} | KG+: {bait.kg_plus:+g} | "
        f"Controle: {bait.control:+.1f}s"
    )




def show_inventory(
    inventory: List[InventoryEntry],
    owned_rods: List[Rod],
    equipped_rod: Rod,
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
    equipped_bait_id: Optional[str],
    cosmetics_state: PlayerCosmeticsState,
    on_cosmetics_changed: Optional[Callable[[], None]] = None,
    hunt_fish_names: Optional[set[str]] = None,
) -> tuple[Rod, Optional[str]]:
    page_size = 12
    page = 0

    def sanitize_equipped_bait() -> None:
        nonlocal equipped_bait_id
        equipped_bait_id = inventory_sanitize_equipped_bait(
            equipped_bait_id,
            bait_inventory,
            bait_by_id,
        )

    def list_owned_baits() -> List[tuple[str, BaitDefinition, int]]:
        return inventory_list_owned_baits(bait_inventory, bait_by_id)

    def active_bait_summary() -> tuple[str, str]:
        return inventory_active_bait_summary(
            equipped_bait_id,
            bait_inventory,
            bait_by_id,
            format_bait_stats,
        )

    def active_cosmetics_summary() -> tuple[str, str]:
        return inventory_active_cosmetics_summary(cosmetics_state)

    def open_cosmetics_menu() -> None:
        while True:
            clear_screen()
            active_color, active_icon = active_cosmetics_summary()
            icon_color_def = UI_COLOR_DEFINITIONS.get(cosmetics_state.equipped_icon_color)
            active_icon_color = (
                icon_color_def.name
                if icon_color_def is not None
                else cosmetics_state.equipped_icon_color
            )
            print_menu_panel(
                "COSMETICOS",
                subtitle="Visual da interface",
                header_lines=[
                    f"Cor ativa: {active_color}",
                    f"Cor do icone: {active_icon_color}",
                    f"Icone ativo: {active_icon}",
                    f"Cores desbloqueadas: {len(cosmetics_state.unlocked_ui_colors)}",
                    f"Icones desbloqueados: {len(cosmetics_state.unlocked_ui_icons)}",
                ],
                options=[
                    MenuOption("1", "Equipar cor"),
                    MenuOption("2", "Equipar icone"),
                    MenuOption("3", "Equipar cor do icone"),
                    MenuOption("0", "Voltar"),
                ],
                prompt="Escolha uma opcao:",
                show_badge=False,
            )
            choice = input("> ").strip()
            if choice == "0":
                return
            if choice == "1":
                unlocked_colors = list_unlocked_ui_colors(cosmetics_state)
                if not unlocked_colors:
                    print("Nenhuma cor desbloqueada.")
                    input("\nEnter para voltar.")
                    continue
                clear_screen()
                print_menu_panel(
                    "EQUIPAR COR",
                    subtitle=f"Atual: {active_color}",
                    options=[
                        MenuOption(
                            str(idx),
                            color.name,
                            status="equipada"
                            if color.color_id == cosmetics_state.equipped_ui_color
                            else "",
                        )
                        for idx, color in enumerate(unlocked_colors, start=1)
                    ],
                    prompt="Digite o numero da cor:",
                    show_badge=False,
                )
                selection = input("> ").strip()
                if not selection.isdigit():
                    print("Entrada invalida.")
                    input("\nEnter para voltar.")
                    continue
                idx = int(selection)
                if not (1 <= idx <= len(unlocked_colors)):
                    print("Numero fora do intervalo.")
                    input("\nEnter para voltar.")
                    continue
                selected = unlocked_colors[idx - 1]
                if equip_ui_color(cosmetics_state, selected.color_id):
                    if on_cosmetics_changed is not None:
                        on_cosmetics_changed()
                    print(f"Cor equipada: {selected.name}.")
                else:
                    print("Nao foi possivel equipar essa cor.")
                input("\nEnter para voltar.")
                continue
            if choice == "2":
                unlocked_icons = list_unlocked_ui_icons(cosmetics_state)
                if not unlocked_icons:
                    print("Nenhum icone desbloqueado.")
                    input("\nEnter para voltar.")
                    continue
                clear_screen()
                print_menu_panel(
                    "EQUIPAR ICONE",
                    subtitle=f"Atual: {active_icon}",
                    options=[
                        MenuOption(
                            str(idx),
                            icon.name,
                            status="equipado"
                            if icon.icon_id == cosmetics_state.equipped_ui_icon
                            else "",
                        )
                        for idx, icon in enumerate(unlocked_icons, start=1)
                    ],
                    prompt="Digite o numero do icone:",
                    show_badge=False,
                )
                selection = input("> ").strip()
                if not selection.isdigit():
                    print("Entrada invalida.")
                    input("\nEnter para voltar.")
                    continue
                idx = int(selection)
                if not (1 <= idx <= len(unlocked_icons)):
                    print("Numero fora do intervalo.")
                    input("\nEnter para voltar.")
                    continue
                selected = unlocked_icons[idx - 1]
                if equip_ui_icon(cosmetics_state, selected.icon_id):
                    if on_cosmetics_changed is not None:
                        on_cosmetics_changed()
                    print(f"Icone equipado: {selected.name}.")
                else:
                    print("Nao foi possivel equipar esse icone.")
                input("\nEnter para voltar.")
                continue
            if choice == "3":
                unlocked_colors = list_unlocked_ui_colors(cosmetics_state)
                if not unlocked_colors:
                    print("Nenhuma cor desbloqueada.")
                    input("\nEnter para voltar.")
                    continue
                clear_screen()
                print_menu_panel(
                    "COR DO ICONE",
                    subtitle=f"Atual: {active_icon_color}",
                    options=[
                        MenuOption(
                            str(idx),
                            color.name,
                            status="equipada"
                            if color.color_id == cosmetics_state.equipped_icon_color
                            else "",
                        )
                        for idx, color in enumerate(unlocked_colors, start=1)
                    ],
                    prompt="Digite o numero da cor:",
                    show_badge=False,
                )
                selection = input("> ").strip()
                if not selection.isdigit():
                    print("Entrada invalida.")
                    input("\nEnter para voltar.")
                    continue
                idx = int(selection)
                if not (1 <= idx <= len(unlocked_colors)):
                    print("Numero fora do intervalo.")
                    input("\nEnter para voltar.")
                    continue
                selected = unlocked_colors[idx - 1]
                if equip_icon_color(cosmetics_state, selected.color_id):
                    if on_cosmetics_changed is not None:
                        on_cosmetics_changed()
                    print(f"Cor do icone equipada: {selected.name}.")
                else:
                    print("Nao foi possivel equipar essa cor para o icone.")
                input("\nEnter para voltar.")
                continue
            print("Opcao invalida.")
            input("\nEnter para voltar.")

    def get_page_bounds() -> tuple[int, int, int]:
        nonlocal page
        page_slice = get_page_slice(len(inventory), page, page_size)
        page = page_slice.page
        return page_slice.start, page_slice.end, page_slice.total_pages

    sanitize_equipped_bait()

    if use_modern_ui():
        while True:
            clear_screen()
            sanitize_equipped_bait()
            owned_baits = list_owned_baits()
            start, end, total_pages = get_page_bounds()
            total_kg = sum(entry.kg for entry in inventory)
            active_bait_label, active_bait_stats = active_bait_summary()
            cosmetics_option_key = "4" if equipped_bait_id else "3"
            options = [
                MenuOption("1", "Equipar vara", "Selecionar outra vara"),
                MenuOption(
                    "2",
                    "Equipar isca",
                    "Selecionar isca ativa",
                    enabled=bool(owned_baits),
                ),
            ]
            if equipped_bait_id:
                options.append(MenuOption("3", "Desequipar isca", "Remover isca ativa"))
            options.append(
                MenuOption(
                    cosmetics_option_key,
                    "Cosmeticos",
                    "Cor da interface, cor do icone e icone",
                )
            )
            if total_pages > 1:
                options.extend(
                    [
                        MenuOption(
                            PAGE_NEXT_KEY.upper(),
                            "Proxima pagina",
                            f"Peixes {page + 1}/{total_pages}",
                            enabled=page < total_pages - 1,
                        ),
                        MenuOption(
                            PAGE_PREV_KEY.upper(),
                            "Pagina anterior",
                            f"Peixes {page + 1}/{total_pages}",
                            enabled=page > 0,
                        ),
                    ]
                )
            options.append(MenuOption("0", "Voltar"))
            print_menu_panel(
                "INVENTARIO",
                subtitle="Peixes e equipamento",
                header_lines=[
                    f"Peixes: {len(inventory)} | Peso total: {total_kg:0.2f}kg",
                    f"Vara equipada: {equipped_rod.name}",
                    f"Stats: {format_rod_stats(equipped_rod)}",
                    f"Isca ativa: {active_bait_label}",
                    active_bait_stats if active_bait_stats else "Buff de isca: -",
                ],
                options=options,
                prompt="Escolha uma opcao:",
                show_badge=False,
            )
            if inventory:
                print("")
                print(f"Peixes [{page + 1}/{total_pages}]")
                render_inventory(
                    inventory[start:end],
                    show_title=False,
                    hunt_fish_names=hunt_fish_names,
                    start_index=start + 1,
                )
                if total_pages > 1:
                    print(f"Mostrando {start + 1}-{end} de {len(inventory)}.")

            choice = read_menu_choice(
                "> ",
                instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if total_pages > 1 else set(),
            ).lower()
            if choice == "0":
                return equipped_rod, equipped_bait_id

            page, moved = apply_page_hotkey(choice, page, total_pages)
            if moved:
                continue

            if choice == "1":
                while True:
                    clear_screen()
                    print_menu_panel(
                        "EQUIPAR VARA",
                        subtitle=f"Atual: {equipped_rod.name}",
                        options=[
                            MenuOption(
                                str(idx),
                                rod.name,
                                format_rod_stats(rod),
                                status="equipada" if rod.name == equipped_rod.name else "",
                            )
                            for idx, rod in enumerate(owned_rods, start=1)
                        ],
                        prompt="Digite o numero da vara:",
                        show_badge=False,
                    )
                    selection = input("> ").strip()
                    if not selection.isdigit():
                        print("Entrada invalida.")
                        input("\nEnter para voltar.")
                        continue

                    idx = int(selection)
                    if not (1 <= idx <= len(owned_rods)):
                        print("Numero fora do intervalo.")
                        input("\nEnter para voltar.")
                        continue

                    equipped_rod = owned_rods[idx - 1]
                    print(f"Vara equipada: {equipped_rod.name}.")
                    input("\nEnter para voltar.")
                    break
                continue

            if choice == "2":
                if not owned_baits:
                    print("Voce nao possui iscas.")
                    input("\nEnter para voltar.")
                    continue
                while True:
                    clear_screen()
                    print_menu_panel(
                        "EQUIPAR ISCA",
                        subtitle=f"Atual: {active_bait_label}",
                        options=[
                            MenuOption(
                                str(idx),
                                bait.name,
                                f"x{quantity} | {format_bait_stats(bait)}",
                                status="equipada" if bait_id == equipped_bait_id else "",
                            )
                            for idx, (bait_id, bait, quantity) in enumerate(owned_baits, start=1)
                        ],
                        prompt="Digite o numero da isca:",
                        show_badge=False,
                    )
                    selection = input("> ").strip()
                    if not selection.isdigit():
                        print("Entrada invalida.")
                        input("\nEnter para voltar.")
                        continue
                    idx = int(selection)
                    if not (1 <= idx <= len(owned_baits)):
                        print("Numero fora do intervalo.")
                        input("\nEnter para voltar.")
                        continue
                    selected_bait_id, selected_bait, _ = owned_baits[idx - 1]
                    equipped_bait_id = selected_bait_id
                    print(f"Isca equipada: {selected_bait.name}.")
                    input("\nEnter para voltar.")
                    break
                continue

            if equipped_bait_id and choice == "3":
                equipped_bait_id = None
                print("Isca desequipada.")
                input("\nEnter para voltar.")
                continue

            if choice == cosmetics_option_key:
                open_cosmetics_menu()
                continue

            print("Opcao invalida.")
            input("\nEnter para voltar.")

    while True:
        clear_screen()
        sanitize_equipped_bait()
        owned_baits = list_owned_baits()
        active_bait_label, active_bait_stats = active_bait_summary()
        start, end, total_pages = get_page_bounds()
        print("=== Inventario ===")
        print("\nVara equipada:")
        print(f"- {equipped_rod.name} ({format_rod_stats(equipped_rod)})")
        print("\nIsca ativa:")
        print(f"- {active_bait_label}")
        if active_bait_stats:
            print(f"  {active_bait_stats}")
        cosmetics_option_key = "4" if equipped_bait_id else "3"
        print("\n1. Equipar vara")
        print("2. Equipar isca")
        if equipped_bait_id:
            print("3. Desequipar isca")
        print(f"{cosmetics_option_key}. Cosmeticos")
        if total_pages > 1:
            print(f"{PAGE_NEXT_KEY.upper()}. Proxima pagina de peixes ({page + 1}/{total_pages})")
            print(f"{PAGE_PREV_KEY.upper()}. Pagina anterior de peixes ({page + 1}/{total_pages})")
        print("0. Voltar")

        print("\nPeixes:")
        render_inventory(
            inventory[start:end],
            show_title=False,
            hunt_fish_names=hunt_fish_names,
            start_index=start + 1,
        )
        if total_pages > 1:
            print(f"Mostrando {start + 1}-{end} de {len(inventory)}.")

        choice = read_menu_choice(
            "Escolha uma opcao: ",
            instant_keys={PAGE_PREV_KEY, PAGE_NEXT_KEY} if total_pages > 1 else set(),
        ).lower()
        if choice == "0":
            return equipped_rod, equipped_bait_id

        page, moved = apply_page_hotkey(choice, page, total_pages)
        if moved:
            continue

        if choice == "1":
            clear_screen()
            print("Escolha a vara para equipar:")
            for idx, rod in enumerate(owned_rods, start=1):
                selected_marker = " (equipada)" if rod.name == equipped_rod.name else ""
                print(f"{idx}. {rod.name} - {format_rod_stats(rod)}{selected_marker}")
                print(f"   {rod.description}")

            selection = input("Digite o numero da vara: ").strip()
            if not selection.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(owned_rods)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            equipped_rod = owned_rods[idx - 1]
            print(f"Vara equipada: {equipped_rod.name}.")
            input("\nEnter para voltar.")
            continue

        if choice == "2":
            if not owned_baits:
                print("Voce nao possui iscas.")
                input("\nEnter para voltar.")
                continue
            clear_screen()
            print("Escolha a isca para equipar:")
            for idx, (bait_id, bait, quantity) in enumerate(owned_baits, start=1):
                selected_marker = " (equipada)" if bait_id == equipped_bait_id else ""
                print(
                    f"{idx}. [{bait.rarity}] {bait.name} x{quantity}{selected_marker} - "
                    f"{format_bait_stats(bait)}"
                )

            selection = input("Digite o numero da isca: ").strip()
            if not selection.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(owned_baits)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            selected_bait_id, selected_bait, _ = owned_baits[idx - 1]
            equipped_bait_id = selected_bait_id
            print(f"Isca equipada: {selected_bait.name}.")
            input("\nEnter para voltar.")
            continue

        if equipped_bait_id and choice == "3":
            equipped_bait_id = None
            print("Isca desequipada.")
            input("\nEnter para voltar.")
            continue

        if choice == cosmetics_option_key:
            open_cosmetics_menu()
            continue

        print("Opcao invalida.")
        input("\nEnter para voltar.")


def run_fishing_round(
    selected_pool: FishingPool,
    inventory: List[InventoryEntry],
    discovered_fish: set[str],
    equipped_rod: Rod,
    bait_inventory: Dict[str, int],
    bait_by_id: Dict[str, BaitDefinition],
    equipped_bait_id: Optional[str],
    mutations: List[Mutation],
    level: int,
    xp: int,
    event_manager: Optional[EventManager],
    hunt_manager: Optional[HuntManager],
    on_fish_caught: Optional[Callable[[FishProfile, Optional[Mutation]], None]] = None,
) -> tuple[int, int, Optional[str]]:
    recent_catch_times: deque[float] = deque()

    def prune_recent_catch_times(now_s: float) -> None:
        while recent_catch_times and now_s - recent_catch_times[0] > PACE_WINDOW_S:
            recent_catch_times.popleft()

    def flush_runtime_notifications() -> None:
        if event_manager:
            event_manager.suppress_notifications(False)
            for note in event_manager.pop_notifications():
                print(f"\n🔔 {note}")
        if hunt_manager:
            hunt_manager.suppress_notifications(False)
            for note in hunt_manager.pop_notifications():
                print(f"\n🔔 {note}")

    while True:
        if event_manager:
            event_manager.suppress_notifications(True)
        if hunt_manager:
            hunt_manager.suppress_notifications(True)
        clear_screen()
        equipped_bait_id, active_bait, active_bait_quantity = resolve_active_bait(
            bait_inventory,
            bait_by_id,
            equipped_bait_id,
        )
        effective_control, effective_luck, effective_kg_max = calculate_effective_rod_stats(
            equipped_rod,
            active_bait,
        )
        print("=== Pesca (WASD em tempo real) ===")
        print(f"Pool selecionada: {selected_pool.name}")
        print(f"Vara equipada: {equipped_rod.name}")
        if active_bait:
            print(f"Isca ativa: {active_bait.name} x{active_bait_quantity}")
            print(f"Buff da isca: {format_bait_stats(active_bait)}")
        else:
            print("Isca ativa: Nenhuma")
        print()

        ks = KeyStream()
        ks.start()

        active_event = event_manager.get_active_event() if event_manager else None
        event_def = active_event.definition if active_event else None
        active_hunt = (
            hunt_manager.get_active_hunt_for_pool(selected_pool.name)
            if hunt_manager
            else None
        )
        hunt_def = active_hunt.definition if active_hunt else None
        hunt_fish = hunt_def.fish_profiles if hunt_def else []
        combined_fish = combine_fish_profiles(selected_pool, event_def, hunt_def)
        eligible_fish = filter_eligible_fish(combined_fish, kg_max=effective_kg_max)
        if not eligible_fish:
            ks.stop()
            print("Nenhum peixe desta pool pode ser fisgado com o setup atual.")
            flush_input_buffer()
            flush_runtime_notifications()
            input("\nEnter para voltar ao menu.")
            return level, xp, equipped_bait_id

        if event_def or hunt_def:
            combined_rarities = sorted({fish.rarity for fish in eligible_fish})
            combined_weights = normalize_rarity_weights(
                selected_pool.rarity_weights,
                combined_rarities,
            )
            if event_def:
                combined_weights = combine_rarity_weights(
                    combined_weights,
                    event_def.rarity_weights,
                    combined_rarities,
                )
            if hunt_def:
                combined_weights = combine_rarity_weights(
                    combined_weights,
                    hunt_def.rarity_weights,
                    combined_rarities,
                )
        else:
            combined_weights = selected_pool.rarity_weights

        rod_luck = effective_luck * (event_def.luck_multiplier if event_def else 1.0)
        fish = selected_pool.choose_fish(
            eligible_fish,
            rod_luck,
            rarity_weights_override=combined_weights,
        )
        is_hunt_fish = any(fish is hunt_candidate for hunt_candidate in hunt_fish)
        attempt = fish.generate_attempt()
        now_s = time.monotonic()
        prune_recent_catch_times(now_s)
        pace_multiplier = _reel_time_multiplier_from_pace(len(recent_catch_times))
        base_time_limit_s = max(0.5, attempt.time_limit_s + effective_control)
        attempt = FishingAttempt(
            sequence=attempt.sequence,
            time_limit_s=max(0.5, base_time_limit_s * pace_multiplier),
            allowed_keys=attempt.allowed_keys,
        )
        game = FishingMiniGame(
            attempt,
            can_slash=equipped_rod.can_slash,
            slash_chance=equipped_rod.slash_chance,
            slash_power=equipped_rod.slash_power,
            can_slam=equipped_rod.can_slam,
            slam_chance=equipped_rod.slam_chance,
            slam_time_bonus=equipped_rod.slam_time_bonus,
        )
        game.begin()

        consumed_bait_name: Optional[str] = None
        consumed_bait_remaining = 0
        if active_bait and equipped_bait_id:
            consumed_bait_name = active_bait.name
            consumed_bait_remaining = max(0, bait_inventory.get(equipped_bait_id, 0) - 1)
            if consumed_bait_remaining <= 0:
                bait_inventory.pop(equipped_bait_id, None)
                equipped_bait_id = None
            else:
                bait_inventory[equipped_bait_id] = consumed_bait_remaining

        print("\n🐟 O peixe mordeu! Complete a sequência:")

        if consumed_bait_name is not None:
            print(
                f"Isca consumida: {consumed_bait_name} "
                f"(restante: {consumed_bait_remaining})"
            )

        if pace_multiplier < 1.0:
            print(
                "Pace penalty active: reaction window at "
                f"{pace_multiplier * 100:0.0f}%."
            )

        result: Optional[FishingResult] = None

        while result is None:
            if ks.stop_requested():
                result = FishingResult(
                    False,
                    "Saiu da pesca (ESC)",
                    game.typed[:],
                    time.perf_counter() - game.start_time,
                )
                break

            for ch in ks.pop_all():
                result = game.handle_key(ch)
                if result is not None:
                    break

            if result is None:
                result = game.check_timeout()

            render(
                attempt,
                game.typed,
                game.time_left(),
                total_time_s=game.total_time_limit(),
            )
            time.sleep(0.016)

        print()
        ks.stop()

        if result.success:
            catch_time_s = time.monotonic()
            recent_catch_times.append(catch_time_s)
            prune_recent_catch_times(catch_time_s)
            first_catch = fish.name not in discovered_fish
            caught_kg = random.uniform(fish.kg_min, fish.kg_max)
            if caught_kg > effective_kg_max:
                caught_kg = effective_kg_max
            event_mutations = event_def.mutations if event_def else []
            eligible_mutations = filter_mutations_for_rod(
                list(mutations) + list(event_mutations),
                equipped_rod.name,
            )
            mutation = choose_mutation(eligible_mutations)
            mutation_name = mutation.name if mutation else None
            mutation_xp_multiplier = mutation.xp_multiplier if mutation else 1.0
            mutation_gold_multiplier = mutation.gold_multiplier if mutation else 1.0
            inventory.append(
                InventoryEntry(
                    name=fish.name,
                    rarity=fish.rarity,
                    kg=caught_kg,
                    base_value=fish.base_value,
                    mutation_name=mutation_name,
                    mutation_xp_multiplier=mutation_xp_multiplier,
                    mutation_gold_multiplier=mutation_gold_multiplier,
                    is_hunt=is_hunt_fish,
                )
            )
            if on_fish_caught:
                on_fish_caught(fish, mutation)
            if hunt_manager:
                hunt_manager.record_catch(selected_pool.name)
            discovered_fish.add(fish.name)
            base_xp = xp_for_rarity(fish.rarity)
            event_xp_multiplier = event_def.xp_multiplier if event_def else 1.0
            gained_xp = max(
                1,
                int(round(base_xp * mutation_xp_multiplier * event_xp_multiplier)),
            )
            level, xp, level_ups = apply_xp_gain(level, xp, gained_xp)
            fish_name_label = (
                f"{Fore.RED}{fish.name}{Style.RESET_ALL}"
                if is_hunt_fish
                else fish.name
            )
            print(f"🎣 Você pescou: {fish_name_label} [{fish.rarity}] - {caught_kg:0.2f}kg")
            if first_catch:
                print(f"📘 Primeira captura registrada no bestiário: {fish_name_label}!")
            if mutation:
                print(
                    "🧬 Mutação: "
                    f"{mutation.name} (x{mutation_xp_multiplier:0.2f} XP | "
                    f"x{mutation_gold_multiplier:0.2f} Gold)"
                )
            print(f"✨ Ganhou {gained_xp} XP.")
            if level_ups:
                print(f"⬆️  Subiu {level_ups} nível(is)! Agora está no nível {level}.")
        else:
            print(f"❌ {result.reason}  ({result.elapsed_s:0.2f}s)")
            print(f"Sequência era: {' '.join(attempt.sequence)}")
            if result.typed:
                print(f"Você digitou:  {' '.join(result.typed)}")

        flush_runtime_notifications()
        flush_input_buffer()
        while True:
            print("\n1. Pescar novamente")
            print("0. Voltar ao menu")
            choice = input("Escolha uma opção: ").strip()
            if choice == "1":
                if event_manager:
                    event_manager.suppress_notifications(True)
                if hunt_manager:
                    hunt_manager.suppress_notifications(True)
                break
            if choice == "0" or choice == "":
                return level, xp, equipped_bait_id
            print("Opção inválida.")

    return level, xp, equipped_bait_id



def main(dev_mode: bool = False):
    if hasattr(sys.stdout, "reconfigure"):
        # Prevent UnicodeEncodeError on terminals using legacy encodings.
        sys.stdout.reconfigure(errors="replace")
    colorama_init(autoreset=True)
    random.seed()

    base_dir = Path(__file__).resolve().parent.parent / "pools"
    pools = load_pools(base_dir)
    events_dir = Path(__file__).resolve().parent.parent / "events"
    events = load_events(events_dir)
    event_manager = EventManager(events, dev_tools_enabled=dev_mode)
    hunts_dir = Path(__file__).resolve().parent.parent / "hunts"
    hunts = load_hunts(
        hunts_dir,
        valid_pool_names={pool.name for pool in pools},
    )
    hunt_manager = HuntManager(hunts, dev_tools_enabled=dev_mode)
    event_manager.start()
    rods_dir = Path(__file__).resolve().parent.parent / "rods"
    available_rods = load_rods(rods_dir)
    mutations_dir = Path(__file__).resolve().parent.parent / "mutations"
    available_mutations = load_mutations(mutations_dir)
    baits_dir = Path(__file__).resolve().parent.parent / "baits"
    bait_crates = load_bait_crates(baits_dir)
    bait_by_id = build_bait_lookup(bait_crates)
    starter_rod = select_starter_rod(available_rods)
    owned_rods = [starter_rod]
    equipped_rod = starter_rod
    unlocked_rods = build_default_unlocked_rods(available_rods, starter_rod)
    selected_pool = select_default_pool(pools)
    unlocked_pools = build_default_unlocked_pools(pools, selected_pool)
    missions_dir = Path(__file__).resolve().parent.parent / "missions"
    missions = load_missions(missions_dir)
    mission_state = restore_mission_state(None, missions)
    mission_progress = MissionProgress()
    bestiary_rewards_dir = Path(__file__).resolve().parent.parent / "bestiary_rewards"
    bestiary_rewards = load_bestiary_rewards(bestiary_rewards_dir)
    bestiary_reward_state = BestiaryRewardState()
    crafting_dir = Path(__file__).resolve().parent.parent / "crafting"
    crafting_definitions = load_crafting_definitions(
        crafting_dir,
        valid_rod_names={rod.name for rod in available_rods},
    )
    crafting_state = restore_crafting_state(None, crafting_definitions)
    crafting_progress = CraftingProgress()
    cosmetics_state = create_default_cosmetics_state()
    inventory: List[InventoryEntry] = []
    bait_inventory: Dict[str, int] = {}
    equipped_bait_id: Optional[str] = None
    discovered_fish: set[str] = set()
    balance = 0.0
    level = 1
    xp = 0
    pool_market_orders = {}

    save_path = get_default_save_path()
    save_data = load_game(save_path)
    if save_data:
        clear_screen()
        print("Um save foi encontrado. Carregando automaticamente...")
        inventory = restore_inventory(save_data.get("inventory"))
        discovered_fish = restore_discovered_fish(
            save_data.get("discovered_fish"),
            inventory,
        )
        balance = restore_balance(save_data.get("balance"), balance)
        owned_rods = restore_owned_rods(save_data.get("owned_rods"), available_rods, starter_rod)
        unlocked_rods_raw = save_data.get("unlocked_rods")
        default_unlocked_rods = {rod.name for rod in available_rods if rod.unlocked_default}
        if isinstance(unlocked_rods_raw, list):
            available_rod_names = {rod.name for rod in available_rods}
            unlocked_rods = {
                name for name in unlocked_rods_raw if isinstance(name, str) and name in available_rod_names
            }
            unlocked_rods.update(default_unlocked_rods)
        else:
            unlocked_rods = {rod.name for rod in owned_rods} | default_unlocked_rods
        selected_pool = restore_selected_pool(save_data.get("selected_pool"), pools, selected_pool)
        unlocked_pools = set(
            restore_unlocked_pools(save_data.get("unlocked_pools"), pools, selected_pool)
        )
        unlocked_pools.update({pool.name for pool in pools if pool.unlocked_default})
        equipped_rod = restore_equipped_rod(
            save_data.get("equipped_rod"),
            owned_rods,
            starter_rod,
        )
        level = restore_level(save_data.get("level"), level)
        xp = restore_xp(save_data.get("xp"), xp)
        mission_state = restore_mission_state(save_data.get("mission_state"), missions)
        mission_progress = restore_mission_progress(save_data.get("mission_progress"))
        crafting_state = restore_crafting_state(save_data.get("crafting_state"), crafting_definitions)
        crafting_progress = restore_crafting_progress(save_data.get("crafting_progress"))
        pool_market_orders = restore_pool_market_orders(save_data.get("pool_market_orders"))
        bait_inventory = restore_bait_inventory(save_data.get("bait_inventory"), bait_by_id)
        equipped_bait_id = restore_equipped_bait(
            save_data.get("equipped_bait"),
            bait_inventory,
            bait_by_id,
        )
        bestiary_reward_state = restore_bestiary_reward_state(
            save_data.get("bestiary_reward_state"),
            bestiary_rewards,
        )
        cosmetics_state = restore_cosmetics_state(save_data.get("cosmetics_state"))
        hunt_manager.restore_state(restore_hunt_state(save_data.get("hunt_state")))
        print("Save carregado com sucesso!")
        time.sleep(1)

    hunt_manager.start()

    def apply_active_cosmetics() -> None:
        ui_color_def = UI_COLOR_DEFINITIONS.get(cosmetics_state.equipped_ui_color)
        icon_color_def = UI_COLOR_DEFINITIONS.get(cosmetics_state.equipped_icon_color)
        icon_def = UI_ICON_DEFINITIONS.get(cosmetics_state.equipped_ui_icon)
        set_ui_cosmetics(
            accent_color=ui_color_def.accent_color if ui_color_def is not None else Fore.CYAN,
            icon_color=(
                icon_color_def.accent_color
                if icon_color_def is not None
                else (ui_color_def.accent_color if ui_color_def is not None else Fore.CYAN)
            ),
            badge_lines=icon_def.badge_lines if icon_def is not None else None,
        )

    apply_active_cosmetics()

    fish_by_name: Dict[str, FishProfile] = {
        fish.name: fish
        for pool in pools
        for fish in pool.fish_profiles
    }
    event_fish_profiles = [
        fish
        for event in events
        for fish in event.fish_profiles
    ]
    hunt_fish_profiles = [
        fish
        for hunt in hunts
        for fish in hunt.fish_profiles
    ]
    hunt_fish_names = {fish.name for fish in hunt_fish_profiles}
    for fish in event_fish_profiles:
        fish_by_name.setdefault(fish.name, fish)
    for fish in hunt_fish_profiles:
        fish_by_name.setdefault(fish.name, fish)
    update_mission_completions(
        missions,
        mission_state,
        mission_progress,
        level=level,
        pools=pools,
        discovered_fish=discovered_fish,
    )

    def unlocked_pool_keys() -> set[str]:
        keys = set(unlocked_pools)
        for pool in pools:
            if pool.name in unlocked_pools:
                keys.add(pool.folder.name)
        return keys

    inventory_fish_counts_cache: Dict[str, int] = {}
    inventory_mutation_counts_cache: Dict[str, int] = {}
    inventory_fish_counts_dirty = True

    def mark_inventory_fish_counts_dirty() -> None:
        nonlocal inventory_fish_counts_dirty
        inventory_fish_counts_dirty = True

    def rebuild_inventory_count_caches_if_needed() -> None:
        nonlocal inventory_fish_counts_dirty
        if not inventory_fish_counts_dirty:
            return
        inventory_fish_counts_cache.clear()
        inventory_fish_counts_cache.update(count_inventory_fish(inventory))
        inventory_mutation_counts_cache.clear()
        inventory_mutation_counts_cache.update(count_inventory_mutations(inventory))
        inventory_fish_counts_dirty = False

    def get_inventory_fish_counts() -> Dict[str, int]:
        rebuild_inventory_count_caches_if_needed()
        return inventory_fish_counts_cache

    def get_inventory_mutation_counts() -> Dict[str, int]:
        rebuild_inventory_count_caches_if_needed()
        return inventory_mutation_counts_cache

    def refresh_crafting_unlocks(print_notifications: bool = False) -> List[str]:
        newly_unlocked = update_crafting_unlocks(
            crafting_definitions,
            crafting_state,
            crafting_progress,
            level=level,
            pools=pools,
            discovered_fish=discovered_fish,
            unlocked_pools=unlocked_pool_keys(),
            mission_state=mission_state,
            unlocked_rods=unlocked_rods,
            play_time_seconds=mission_progress.play_time_seconds,
            inventory_fish_counts=get_inventory_fish_counts(),
            inventory_mutation_counts=get_inventory_mutation_counts(),
        )
        notes = [
            f"Nova receita desbloqueada: {definition.rod_name}"
            for definition in newly_unlocked
        ]
        if print_notifications:
            for note in notes:
                print(f"\n🔔 {note}")
        return notes

    def on_fish_caught_for_progress(fish: FishProfile, mutation: Optional[Mutation]) -> None:
        mutation_name = mutation.name if mutation else None
        mission_progress.record_fish_caught(fish.name, mutation_name)
        crafting_progress.record_find(fish.name, mutation_name)
        mark_inventory_fish_counts_dirty()

    def on_market_appraise_completed(entry: InventoryEntry) -> List[str]:
        crafting_progress.record_find(entry.name, entry.mutation_name)
        return refresh_crafting_unlocks(print_notifications=False)

    def apply_bestiary_reward(reward: BestiaryRewardDefinition) -> List[str]:
        nonlocal balance, level, xp
        notes: List[str] = []
        rods_by_name = {rod.name: rod for rod in available_rods}
        for reward_payload in reward.rewards:
            reward_type = reward_payload.get("type")
            if reward_type == "money":
                try:
                    amount = float(reward_payload.get("amount", 0.0))
                except (TypeError, ValueError):
                    amount = 0.0
                if amount > 0:
                    balance += amount
                    mission_progress.record_money_earned(amount)
                    notes.append(f"💰 +R$ {amount:0.2f}")
                continue

            if reward_type == "xp":
                try:
                    amount = int(reward_payload.get("amount", 0))
                except (TypeError, ValueError):
                    amount = 0
                if amount > 0:
                    level, xp, level_ups = apply_xp_gain(level, xp, amount)
                    notes.append(f"✨ +{amount} XP")
                    if level_ups:
                        notes.append(f"⬆️ Subiu {level_ups} nivel(is)!")
                continue

            if reward_type == "bait":
                bait_id = reward_payload.get("bait_id")
                try:
                    amount = int(reward_payload.get("amount", 0))
                except (TypeError, ValueError):
                    amount = 0
                if (
                    isinstance(bait_id, str)
                    and bait_id in bait_by_id
                    and amount > 0
                ):
                    bait_inventory[bait_id] = bait_inventory.get(bait_id, 0) + amount
                    notes.append(f"🪱 +{amount}x {bait_by_id[bait_id].name}")
                continue

            if reward_type == "rod":
                rod_name = reward_payload.get("rod_name")
                if not isinstance(rod_name, str):
                    continue
                rod = rods_by_name.get(rod_name)
                if rod is None:
                    continue
                was_unlocked = rod.name in unlocked_rods
                unlocked_rods.add(rod.name)
                if rod.name not in {owned.name for owned in owned_rods}:
                    owned_rods.append(rod)
                    notes.append(f"🪝 Vara adicionada: {rod.name}")
                elif not was_unlocked:
                    notes.append(f"🪝 Vara desbloqueada: {rod.name}")
                continue

            if reward_type == "ui_color":
                color_id = reward_payload.get("color_id")
                if not isinstance(color_id, str):
                    continue
                if unlock_ui_color(cosmetics_state, color_id):
                    color_def = UI_COLOR_DEFINITIONS[color_id]
                    notes.append(f"Nova cor desbloqueada: {color_def.name}")
                continue

            if reward_type == "ui_icon":
                icon_id = reward_payload.get("icon_id")
                if not isinstance(icon_id, str):
                    continue
                if unlock_ui_icon(cosmetics_state, icon_id):
                    icon_def = UI_ICON_DEFINITIONS[icon_id]
                    notes.append(f"Novo icone desbloqueado: {icon_def.name}")
        return notes

    refresh_crafting_unlocks(print_notifications=False)

    state_ready = True
    exit_requested = False
    autosave_done = False
    loop_start: Optional[float] = None
    play_time_recorded_for_loop = True

    handled_signals = [signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        handled_signals.append(signal.SIGHUP)
    if hasattr(signal, "SIGBREAK"):
        handled_signals.append(signal.SIGBREAK)

    previous_signal_handlers = {
        signum: signal.getsignal(signum)
        for signum in handled_signals
    }

    def request_graceful_exit(signum, _frame):
        signame = signal.Signals(signum).name if signum in signal.Signals.__members__.values() else str(signum)
        print(f"\nRecebido {signame}. Salvando antes de sair...")
        raise KeyboardInterrupt

    for signum in handled_signals:
        signal.signal(signum, request_graceful_exit)

    try:
        while True:
            loop_start = time.monotonic()
            play_time_recorded_for_loop = False
            active_event = event_manager.get_active_event()
            active_hunt = hunt_manager.get_active_hunt_for_pool(selected_pool.name)
            choice = show_main_menu(
                selected_pool,
                balance,
                level,
                xp,
                active_event,
                active_hunt,
                dev_mode=dev_mode,
            )
            if choice == "1":
                level, xp, equipped_bait_id = run_fishing_round(
                    selected_pool,
                    inventory,
                    discovered_fish,
                    equipped_rod,
                    bait_inventory,
                    bait_by_id,
                    equipped_bait_id,
                    available_mutations,
                    level,
                    xp,
                    event_manager,
                    hunt_manager,
                    on_fish_caught=on_fish_caught_for_progress,
                )
                mark_inventory_fish_counts_dirty()
            elif choice == "2":
                clear_screen()
                selected_pool = select_pool(pools, unlocked_pools)
            elif choice == "3":
                equipped_rod, equipped_bait_id = show_inventory(
                    inventory,
                    owned_rods,
                    equipped_rod,
                    bait_inventory,
                    bait_by_id,
                    equipped_bait_id,
                    cosmetics_state,
                    on_cosmetics_changed=apply_active_cosmetics,
                    hunt_fish_names=hunt_fish_names,
                )
            elif choice == "4":
                unlocked_pool_market_keys = {
                    pool.name
                    for pool in pools
                    if pool.name in unlocked_pools
                } | {
                    pool.folder.name
                    for pool in pools
                    if pool.name in unlocked_pools
                }
                balance, level, xp = show_market(
                    inventory,
                    balance,
                    selected_pool,
                    level,
                    xp,
                    available_rods,
                    owned_rods,
                    fish_by_name,
                    available_mutations,
                    equipped_rod=equipped_rod,
                    pools=pools,
                    discovered_fish=discovered_fish,
                    mission_state=mission_state,
                    play_time_seconds=mission_progress.play_time_seconds,
                    crafting_definitions=crafting_definitions,
                    crafting_state=crafting_state,
                    crafting_progress=crafting_progress,
                    bait_crates=bait_crates,
                    bait_inventory=bait_inventory,
                    bait_by_id=bait_by_id,
                    pool_orders=pool_market_orders,
                    unlocked_rods=unlocked_rods,
                    unlocked_pools=unlocked_pool_market_keys,
                    on_money_earned=mission_progress.record_money_earned,
                    on_money_spent=mission_progress.record_money_spent,
                    on_fish_sold=lambda entry: mission_progress.record_fish_sold(entry.name),
                    on_appraise_completed=on_market_appraise_completed,
                )
                mark_inventory_fish_counts_dirty()
            elif choice == "5":
                show_bestiary(
                    pools,
                    available_rods,
                    owned_rods,
                    unlocked_pools,
                    discovered_fish,
                    hunt_definitions=hunts,
                    regionless_fish_profiles=event_fish_profiles,
                    bestiary_rewards=bestiary_rewards,
                    bestiary_reward_state=bestiary_reward_state,
                    on_claim_bestiary_reward=apply_bestiary_reward,
                )
            elif choice == "6":
                level, xp, balance = show_missions_menu(
                    missions,
                    mission_state,
                    mission_progress,
                    level=level,
                    xp=xp,
                    balance=balance,
                    inventory=inventory,
                    pools=pools,
                    discovered_fish=discovered_fish,
                    unlocked_pools=unlocked_pools,
                    unlocked_rods=unlocked_rods,
                    available_rods=available_rods,
                    fish_by_name=fish_by_name,
                )
                mark_inventory_fish_counts_dirty()
            elif choice == "7" and dev_mode:
                (
                    balance,
                    level,
                    xp,
                    selected_pool,
                    equipped_rod,
                    equipped_bait_id,
                ) = show_dev_save_editor(
                    balance=balance,
                    level=level,
                    xp=xp,
                    selected_pool=selected_pool,
                    equipped_rod=equipped_rod,
                    pools=pools,
                    available_rods=available_rods,
                    owned_rods=owned_rods,
                    unlocked_pools=unlocked_pools,
                    unlocked_rods=unlocked_rods,
                    discovered_fish=discovered_fish,
                    inventory=inventory,
                    bait_by_id=bait_by_id,
                    bait_inventory=bait_inventory,
                    equipped_bait_id=equipped_bait_id,
                    fish_by_name=fish_by_name,
                    available_mutations=available_mutations,
                    missions=missions,
                    mission_state=mission_state,
                    mission_progress=mission_progress,
                    event_manager=event_manager,
                    hunt_manager=hunt_manager,
                )
                mark_inventory_fish_counts_dirty()
            elif choice == "0":
                mission_progress.add_play_time(time.monotonic() - loop_start)
                play_time_recorded_for_loop = True
                update_mission_completions(
                    missions,
                    mission_state,
                    mission_progress,
                    level=level,
                    pools=pools,
                    discovered_fish=discovered_fish,
                )
                refresh_crafting_unlocks(print_notifications=True)
                autosave_state(
                    save_path,
                    balance,
                    inventory,
                    bait_inventory,
                    owned_rods,
                    equipped_rod,
                    equipped_bait_id,
                    selected_pool,
                    unlocked_pools,
                    unlocked_rods,
                    level,
                    xp,
                    discovered_fish,
                    mission_state,
                    mission_progress,
                    crafting_state,
                    crafting_progress,
                    pool_market_orders,
                    bestiary_reward_state,
                    cosmetics_state,
                    hunt_manager,
                )
                autosave_done = True
                exit_requested = True
                print("Saindo...")
                break
            else:
                print("Opção inválida.")
                time.sleep(1)
            mission_progress.add_play_time(time.monotonic() - loop_start)
            play_time_recorded_for_loop = True
            update_mission_completions(
                missions,
                mission_state,
                mission_progress,
                level=level,
                pools=pools,
                discovered_fish=discovered_fish,
            )
            refresh_crafting_unlocks(print_notifications=True)
    except KeyboardInterrupt:
        if loop_start is not None and not play_time_recorded_for_loop:
            mission_progress.add_play_time(time.monotonic() - loop_start)
            update_mission_completions(
                missions,
                mission_state,
                mission_progress,
                level=level,
                pools=pools,
                discovered_fish=discovered_fish,
            )
            refresh_crafting_unlocks(print_notifications=False)
        exit_requested = True
    finally:
        for signum, handler in previous_signal_handlers.items():
            signal.signal(signum, handler)
        if not exit_requested:
            exit_requested = True
        if state_ready and exit_requested and not autosave_done:
            autosave_state(
                save_path,
                balance,
                inventory,
                bait_inventory,
                owned_rods,
                equipped_rod,
                equipped_bait_id,
                selected_pool,
                unlocked_pools,
                unlocked_rods,
                level,
                xp,
                discovered_fish,
                mission_state,
                mission_progress,
                crafting_state,
                crafting_progress,
                pool_market_orders,
                bestiary_reward_state,
                cosmetics_state,
                hunt_manager,
            )
        event_manager.stop()
        hunt_manager.stop()


if __name__ == "__main__":
    main()


