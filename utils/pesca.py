import json
import random
import time
import threading
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Callable, Dict, List, Optional

from colorama import init as colorama_init
from pynput import keyboard

from inventory import InventoryEntry, render_inventory

# -----------------------------
# Config / Modelos
# -----------------------------

VALID_KEYS = ["w", "a", "s", "d"]


@dataclass(frozen=True)
class FishingAttempt:
    """Descreve uma tentativa de pesca (o 'quick time event')."""
    sequence: List[str]
    time_limit_s: float  # tempo TOTAL para completar a sequência


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
        return FishingAttempt(sequence=seq, time_limit_s=self.reaction_time_s)


@dataclass
class FishingPool:
    name: str
    fish_profiles: List[FishProfile]
    folder: Path
    description: str
    rarity_weights: Dict[str, int]

    def choose_fish(self) -> FishProfile:
        fish_by_rarity: Dict[str, List[FishProfile]] = {}
        for fish in self.fish_profiles:
            fish_by_rarity.setdefault(fish.rarity, []).append(fish)

        available_rarities = list(fish_by_rarity.keys())
        if not available_rarities:
            raise RuntimeError("Pool sem peixes disponíveis.")

        weights = [self.rarity_weights.get(rarity, 0) for rarity in available_rarities]
        if sum(weights) <= 0:
            weights = [1 for _ in available_rarities]

        selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
        return random.choice(fish_by_rarity[selected_rarity])


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

        fish_dir = pool_dir / "fish"
        if not fish_dir.exists():
            continue

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
            )
        )

    if not pools:
        raise RuntimeError("Nenhuma pool encontrada. Verifique os arquivos em /pools.")

    return pools


def select_pool(pools: List[FishingPool]) -> FishingPool:
    print("Escolha uma pool para pescar:")
    for idx, pool in enumerate(pools, start=1):
        fish_names = ", ".join(fish.name for fish in pool.fish_profiles)
        print(f"{idx}. {pool.name} ({fish_names})")

    while True:
        choice = input("Digite o número da pool: ").strip()
        if not choice.isdigit():
            print("Entrada inválida. Digite apenas o número da pool.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(pools):
            return pools[idx - 1]

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
    def __init__(self, attempt: FishingAttempt):
        self.attempt = attempt
        self.typed: List[str] = []
        self.index = 0
        self.start_time = 0.0

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
        # só considera WASD (ou futuro: allowed set)
        if key not in VALID_KEYS:
            return None

        # timeout
        elapsed = time.perf_counter() - self.start_time
        if elapsed > self.attempt.time_limit_s:
            return FishingResult(False, "Tempo esgotado", self.typed[:], elapsed)

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


def main():
    colorama_init(autoreset=True)
    random.seed()

    base_dir = Path(__file__).resolve().parent.parent / "pools"
    pools = load_pools(base_dir)
    selected_pool = select_pool(pools)
    fishes = selected_pool.fish_profiles
    inventory: List[InventoryEntry] = []

    ks = KeyStream()
    ks.start()

    print("=== Pesca (WASD em tempo real) ===")
    print(f"Pool selecionada: {selected_pool.name}")
    print("Dica: mantenha o foco no terminal. Pressione ESC para sair.\n")

    while True:
        if ks.stop_requested():
            print("\nSaindo...")
            break

        fish = selected_pool.choose_fish()
        attempt = fish.generate_attempt()
        game = FishingMiniGame(attempt)
        game.begin()

        print(f"\nUm {fish.name} mordeu a isca! Complete a sequência:")

        result: Optional[FishingResult] = None

        # loop do mini-game
        while result is None:
            if ks.stop_requested():
                result = FishingResult(False, "Saiu do jogo (ESC)", game.typed[:], time.perf_counter() - game.start_time)
                break

            # processa teclas capturadas desde a última iteração
            for ch in ks.pop_all():
                result = game.handle_key(ch)
                if result is not None:
                    break

            # verifica timeout
            if result is None:
                result = game.check_timeout()

            render(attempt, game.typed, game.time_left())
            time.sleep(0.016)  # ~60 FPS

        # finaliza a linha do render
        print()

        if result.success:
            caught_kg = random.uniform(fish.kg_min, fish.kg_max)
            inventory.append(
                InventoryEntry(
                    name=fish.name,
                    rarity=fish.rarity,
                    kg=caught_kg,
                )
            )
            print(f"✅ {result.reason}  ({result.elapsed_s:0.2f}s)")
            print(f"Peso: {caught_kg:0.2f}kg")
            render_inventory(inventory)
        else:
            print(f"❌ {result.reason}  ({result.elapsed_s:0.2f}s)")
            print(f"Sequência era: {' '.join(attempt.sequence)}")
            if result.typed:
                print(f"Você digitou:  {' '.join(result.typed)}")

        print("\nEnter para tentar de novo, ou ESC para sair.")
        # Aqui a única pausa é para dar "respiro" no loop; como você pediu
        # sem Enter para o QTE, o Enter é só para iniciar a próxima rodada.
        # Se preferir, posso fazer auto-retry com delay.
        while True:
            if ks.stop_requested():
                print("\nSaindo...")
                return
            # Se apertar Enter, começa outra rodada
            for ch in ks.pop_all():
                if ch == "\r" or ch == "\n":
                    break
            else:
                time.sleep(0.05)
                continue
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
