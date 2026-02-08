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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from colorama import init as colorama_init
from pynput import keyboard

from utils.bestiary import show_bestiary
from utils.dialogue import get_menu_line
from utils.inventory import InventoryEntry, render_inventory
from utils.levels import RARITY_XP, apply_xp_gain, xp_for_rarity, xp_required_for_level
from utils.market import (
    restore_pool_market_orders,
    serialize_pool_market_orders,
    show_market,
)
from utils.missions import (
    MissionProgress,
    load_missions,
    restore_mission_progress,
    restore_mission_state,
    serialize_mission_progress,
    serialize_mission_state,
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
from utils.rods import Rod, load_rods
from utils.save_system import (
    get_default_save_path,
    load_game,
    restore_balance,
    restore_discovered_fish,
    restore_equipped_rod,
    restore_inventory,
    restore_level,
    restore_owned_rods,
    restore_selected_pool,
    restore_unlocked_pools,
    restore_xp,
    save_game,
)
from utils.ui import clear_screen

# -----------------------------
# Config / Modelos
# -----------------------------

VALID_KEYS = ["w", "a", "s", "d"]


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

    luck = max(0.0, float(rod_luck))
    if luck <= 0:
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
        luck_boost = luck * (1 + luck)
        multiplier = 1 + (luck_boost * rank_ratio)
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
        with fish_path.open("r", encoding="utf-8") as handle:
            fish_data = json.load(handle)

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

        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

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


def load_pools(base_dir: Path) -> List[FishingPool]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de pools não encontrado: {base_dir}")

    pools: List[FishingPool] = []
    for pool_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        config_path = pool_dir / "pool.json"
        if not config_path.exists():
            continue

        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        fish_profiles = load_fish_profiles_from_dir(pool_dir / "fish")

        if not fish_profiles:
            continue

        available_rarities = sorted({fish.rarity for fish in fish_profiles})
        configured_weights = data.get("rarity_chances", {})
        if not isinstance(configured_weights, dict):
            configured_weights = {}
        rarity_weights = normalize_rarity_weights(configured_weights, available_rarities)

        pools.append(
            FishingPool(
                name=data.get("name", pool_dir.name),
                fish_profiles=fish_profiles,
                folder=pool_dir,
                description=data.get("description", ""),
                rarity_weights=rarity_weights,
                unlocked_default=bool(data.get("unlocked_default", False)),
            )
        )

    if not pools:
        raise RuntimeError("Nenhuma pool encontrada. Verifique os arquivos em /pools.")

    return pools


def select_pool(pools: List[FishingPool], unlocked_pools: set[str]) -> FishingPool:
    available_pools = [pool for pool in pools if pool.name in unlocked_pools]
    print("Escolha uma pool para pescar:")
    for idx, pool in enumerate(available_pools, start=1):
        print(f"{idx}. {pool.name}")
    if not available_pools:
        raise RuntimeError("Nenhuma pool desbloqueada.")

    while True:
        choice = input("Digite o número da pool: ").strip()
        if not choice.isdigit():
            print("Entrada inválida. Digite apenas o número da pool.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(available_pools):
            return available_pools[idx - 1]

        print("Número fora do intervalo. Tente novamente.")


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
    def __init__(self, attempt: FishingAttempt, *, can_slash: bool = False, slash_chance: float = 0.0):
        self.attempt = attempt
        self.typed: List[str] = []
        self.index = 0
        self.start_time = 0.0
        self.can_slash = can_slash
        self.slash_chance = max(0.0, min(1.0, float(slash_chance)))

    def expected_key(self) -> Optional[str]:
        if self.index >= len(self.attempt.sequence):
            return None
        return self.attempt.sequence[self.index]

    def is_done(self) -> bool:
        return self.index >= len(self.attempt.sequence)

    def time_left(self) -> float:
        elapsed = time.perf_counter() - self.start_time
        return max(0.0, self.attempt.time_limit_s - elapsed)

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
        if elapsed > self.attempt.time_limit_s:
            return FishingResult(False, "Tempo esgotado", self.typed[:], elapsed)

        min_slash_index = self.index + 2
        if self.can_slash and self.slash_chance > 0 and min_slash_index < len(self.attempt.sequence):
            if random.random() <= self.slash_chance:
                remove_index = random.randrange(min_slash_index, len(self.attempt.sequence))
                self.attempt.sequence.pop(remove_index)
                if self.is_done():
                    elapsed = time.perf_counter() - self.start_time
                    return FishingResult(True, "Capturou o peixe!", self.typed[:], elapsed)

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
        if elapsed > self.attempt.time_limit_s and not self.is_done():
            return FishingResult(False, "Tempo esgotado", self.typed[:], elapsed)
        return None


# -----------------------------
# UI simples de terminal
# -----------------------------

def render(attempt: FishingAttempt, typed: List[str], time_left: float):
    seq = attempt.sequence
    idx = len(typed)

    # Mostra apenas as teclas restantes
    remaining = seq[idx:]
    seq_str = " ".join(k.upper() for k in remaining) if remaining else "✔"

    # Barra de tempo
    total = attempt.time_limit_s
    ratio = max(0.0, min(1.0, time_left / total))
    bar_len = 20
    filled = int(bar_len * ratio)
    bar = "█" * filled + " " * (bar_len - filled)

    print("\r" + " " * 120, end="")
    print(
        f"\rSeq: {seq_str:<15} "
        f"Tempo: [{bar}] {time_left:0.2f}s   (ESC sai)",
        end=""
    )

def show_main_menu(
    selected_pool: FishingPool,
    level: int,
    xp: int,
    active_event: Optional[ActiveEvent],
) -> str:
    clear_screen()
    print("🎣 === Menu Principal ===")
    print(get_menu_line())
    print(f"Pool atual: {selected_pool.name}")
    print(f"Nível: {level} | XP: {xp}/{xp_required_for_level(level)}")
    if active_event:
        time_left = math.ceil(active_event.time_left() / 60)
        event = active_event.definition
        print(
            f"🌟 Evento ativo: {event.name} "
            f"({time_left} min restantes)"
        )
        if event.description:
            print(f"   {event.description}")
        print(
            "   "
            f"Sorte x{event.luck_multiplier:0.2f} | "
            f"XP x{event.xp_multiplier:0.2f}"
        )
    print("1. Pescar")
    print("2. Pools")
    print("3. Inventário")
    print("4. Mercado")
    print("5. Bestiário")
    print("6. Missões")
    print("0. Sair")
    return input("Escolha uma opção: ").strip()


def autosave_state(
    save_path: Path,
    balance: float,
    inventory: List[InventoryEntry],
    owned_rods: List[Rod],
    equipped_rod: Rod,
    selected_pool: FishingPool,
    unlocked_pools: set[str],
    unlocked_rods: set[str],
    level: int,
    xp: int,
    discovered_fish: set[str],
    mission_state,
    mission_progress: MissionProgress,
    pool_market_orders,
) -> None:
    save_game(
        save_path,
        balance=balance,
        inventory=inventory,
        owned_rods=owned_rods,
        equipped_rod=equipped_rod,
        selected_pool=selected_pool,
        unlocked_pools=sorted(unlocked_pools),
        unlocked_rods=sorted(unlocked_rods),
        level=level,
        xp=xp,
        discovered_fish=sorted(discovered_fish),
        mission_state=serialize_mission_state(mission_state),
        mission_progress=serialize_mission_progress(mission_progress),
        pool_market_orders=serialize_pool_market_orders(pool_market_orders),
    )


def format_rod_stats(rod: Rod) -> str:
    return (
        f"Sorte: {rod.luck:.0%} | KGMax: {rod.kg_max:g} | "
        f"Controle: {rod.control:+.1f}s"
    )




def show_inventory(
    inventory: List[InventoryEntry],
    owned_rods: List[Rod],
    equipped_rod: Rod,
) -> Rod:
    while True:
        clear_screen()
        print("=== Inventário ===")
        print("\nPeixes:")
        render_inventory(inventory, show_title=False)
        print("\nVara equipada:")
        print(f"- {equipped_rod.name} ({format_rod_stats(equipped_rod)})")
        print("\n1. Equipar vara")
        print("0. Voltar")

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return equipped_rod

        if choice == "1":
            clear_screen()
            print("Escolha a vara para equipar:")
            for idx, rod in enumerate(owned_rods, start=1):
                selected_marker = " (equipada)" if rod.name == equipped_rod.name else ""
                print(f"{idx}. {rod.name} - {format_rod_stats(rod)}{selected_marker}")
                print(f"   {rod.description}")

            selection = input("Digite o número da vara: ").strip()
            if not selection.isdigit():
                print("Entrada inválida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(owned_rods)):
                print("Número fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            equipped_rod = owned_rods[idx - 1]
            print(f"Vara equipada: {equipped_rod.name}.")
            input("\nEnter para voltar.")
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")


def run_fishing_round(
    selected_pool: FishingPool,
    inventory: List[InventoryEntry],
    discovered_fish: set[str],
    equipped_rod: Rod,
    mutations: List[Mutation],
    level: int,
    xp: int,
    event_manager: Optional[EventManager],
    on_fish_caught: Optional[Callable[[FishProfile, Optional[Mutation]], None]] = None,
):
    while True:
        if event_manager:
            event_manager.suppress_notifications(True)
        clear_screen()
        print("🎣 === Pesca (WASD em tempo real) ===")
        print(f"Pool selecionada: {selected_pool.name}")
        print(f"Vara equipada: {equipped_rod.name}")
        print()

        ks = KeyStream()
        ks.start()

        active_event = event_manager.get_active_event() if event_manager else None
        event_def = active_event.definition if active_event else None
        event_fish = event_def.fish_profiles if event_def else []
        combined_fish = list(selected_pool.fish_profiles) + list(event_fish)
        eligible_fish = [
            fish for fish in combined_fish if fish.kg_min <= equipped_rod.kg_max
        ]
        if not eligible_fish:
            ks.stop()
            print("Nenhum peixe desta pool pode ser fisgado com a vara equipada.")
            flush_input_buffer()
            if event_manager:
                event_manager.suppress_notifications(False)
                for note in event_manager.pop_notifications():
                    print(f"\n🔔 {note}")
            input("\nEnter para voltar ao menu.")
            return level, xp

        if event_def:
            combined_rarities = sorted({fish.rarity for fish in eligible_fish})
            combined_weights = combine_rarity_weights(
                selected_pool.rarity_weights,
                event_def.rarity_weights,
                combined_rarities,
            )
        else:
            combined_weights = selected_pool.rarity_weights

        rod_luck = equipped_rod.luck * (event_def.luck_multiplier if event_def else 1.0)
        rod_luck = max(0.0, rod_luck)
        fish = selected_pool.choose_fish(
            eligible_fish,
            rod_luck,
            rarity_weights_override=combined_weights,
        )
        attempt = fish.generate_attempt()
        attempt = FishingAttempt(
            sequence=attempt.sequence,
            time_limit_s=max(0.5, attempt.time_limit_s + equipped_rod.control),
            allowed_keys=attempt.allowed_keys,
        )
        game = FishingMiniGame(
            attempt,
            can_slash=equipped_rod.can_slash,
            slash_chance=equipped_rod.slash_chance,
        )
        game.begin()

        print("\n🐟 O peixe mordeu! Complete a sequência:")

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

            render(attempt, game.typed, game.time_left())
            time.sleep(0.016)

        print()
        ks.stop()

        if result.success:
            caught_kg = random.uniform(fish.kg_min, fish.kg_max)
            if caught_kg > equipped_rod.kg_max:
                caught_kg = equipped_rod.kg_max
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
                )
            )
            if on_fish_caught:
                on_fish_caught(fish, mutation)
            discovered_fish.add(fish.name)
            base_xp = xp_for_rarity(fish.rarity)
            event_xp_multiplier = event_def.xp_multiplier if event_def else 1.0
            gained_xp = max(
                1,
                int(round(base_xp * mutation_xp_multiplier * event_xp_multiplier)),
            )
            level, xp, level_ups = apply_xp_gain(level, xp, gained_xp)
            print(f"🎣 Você pescou: {fish.name} [{fish.rarity}] - {caught_kg:0.2f}kg")
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

        if event_manager:
            event_manager.suppress_notifications(False)
            for note in event_manager.pop_notifications():
                print(f"\n🔔 {note}")

        flush_input_buffer()
        while True:
            print("\n1. Pescar novamente")
            print("0. Voltar ao menu")
            choice = input("Escolha uma opção: ").strip()
            if choice == "1":
                if event_manager:
                    event_manager.suppress_notifications(True)
                break
            if choice == "0" or choice == "":
                return level, xp
            print("Opção inválida.")

    return level, xp



def main():
    colorama_init(autoreset=True)
    random.seed()

    base_dir = Path(__file__).resolve().parent.parent / "pools"
    pools = load_pools(base_dir)
    events_dir = Path(__file__).resolve().parent.parent / "events"
    events = load_events(events_dir)
    event_manager = EventManager(events)
    event_manager.start()
    rods_dir = Path(__file__).resolve().parent.parent / "rods"
    available_rods = load_rods(rods_dir)
    mutations_dir = Path(__file__).resolve().parent.parent / "mutations"
    available_mutations = load_mutations(mutations_dir)
    starter_rod = min(available_rods, key=lambda rod: rod.price)
    owned_rods = [starter_rod]
    equipped_rod = starter_rod
    unlocked_rods = {
        rod.name for rod in available_rods if rod.unlocked_default
    } | {starter_rod.name}
    selected_pool = next(
        (pool for pool in pools if pool.folder.name.lower() == "lagoa"),
        pools[0],
    )
    unlocked_pools = {
        pool.name for pool in pools if pool.unlocked_default
    } | {selected_pool.name}
    missions_dir = Path(__file__).resolve().parent.parent / "missions"
    missions = load_missions(missions_dir)
    mission_state = restore_mission_state(None, missions)
    mission_progress = MissionProgress()
    inventory: List[InventoryEntry] = []
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
        pool_market_orders = restore_pool_market_orders(save_data.get("pool_market_orders"))
        print("Save carregado com sucesso!")
        time.sleep(1)

    fish_by_name = {
        fish.name: fish
        for pool in pools
        for fish in pool.fish_profiles
    }
    update_mission_completions(
        missions,
        mission_state,
        mission_progress,
        level=level,
        pools=pools,
        discovered_fish=discovered_fish,
    )
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
            choice = show_main_menu(selected_pool, level, xp, active_event)
            if choice == "1":
                level, xp = run_fishing_round(
                    selected_pool,
                    inventory,
                    discovered_fish,
                    equipped_rod,
                    available_mutations,
                    level,
                    xp,
                    event_manager,
                    on_fish_caught=lambda fish, mutation: mission_progress.record_fish_caught(
                        fish.name,
                        mutation.name if mutation else None,
                    ),
                )
            elif choice == "2":
                clear_screen()
                selected_pool = select_pool(pools, unlocked_pools)
            elif choice == "3":
                equipped_rod = show_inventory(inventory, owned_rods, equipped_rod)
            elif choice == "4":
                balance, level, xp = show_market(
                    inventory,
                    balance,
                    selected_pool,
                    level,
                    xp,
                    available_rods,
                    owned_rods,
                    pool_orders=pool_market_orders,
                    unlocked_rods=unlocked_rods,
                    on_money_earned=mission_progress.record_money_earned,
                )
            elif choice == "5":
                show_bestiary(
                    pools,
                    available_rods,
                    owned_rods,
                    unlocked_pools,
                    discovered_fish,
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
                autosave_state(
                    save_path,
                    balance,
                    inventory,
                    owned_rods,
                    equipped_rod,
                    selected_pool,
                    unlocked_pools,
                    unlocked_rods,
                    level,
                    xp,
                    discovered_fish,
                    mission_state,
                    mission_progress,
                    pool_market_orders,
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
                owned_rods,
                equipped_rod,
                selected_pool,
                unlocked_pools,
                unlocked_rods,
                level,
                xp,
                discovered_fish,
                mission_state,
                mission_progress,
                pool_market_orders,
            )
        event_manager.stop()


if __name__ == "__main__":
    main()
