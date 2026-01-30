import random
import time
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

from pynput import keyboard


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
        sequence_len_range=(4, 8),
        time_limit_range_s=(2.5, 5.0),
        allowed_keys=None,
        generator: Optional[Callable[[], FishingAttempt]] = None,
    ):
        self.name = name
        self.sequence_len_range = sequence_len_range
        self.time_limit_range_s = time_limit_range_s
        self.allowed_keys = allowed_keys or VALID_KEYS

        # Se quiser, pode plugar um gerador customizado por peixe.
        self._custom_generator = generator

    def generate_attempt(self) -> FishingAttempt:
        if self._custom_generator:
            return self._custom_generator()

        length = random.randint(*self.sequence_len_range)
        seq = [random.choice(self.allowed_keys) for _ in range(length)]
        limit = random.uniform(*self.time_limit_range_s)
        return FishingAttempt(sequence=seq, time_limit_s=limit)


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
    random.seed()

    fishes = [
        FishProfile("Tilápia", sequence_len_range=(4, 6), time_limit_range_s=(2.5, 4.0)),
        FishProfile("Dourado", sequence_len_range=(6, 9), time_limit_range_s=(3.0, 5.0)),
        FishProfile("Tucunaré", sequence_len_range=(5, 8), time_limit_range_s=(2.8, 4.5)),
    ]

    ks = KeyStream()
    ks.start()

    print("=== Pesca (WASD em tempo real) ===")
    print("Dica: mantenha o foco no terminal. Pressione ESC para sair.\n")

    while True:
        if ks.stop_requested():
            print("\nSaindo...")
            break

        fish = random.choice(fishes)
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
            print(f"✅ {result.reason}  ({result.elapsed_s:0.2f}s)")
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