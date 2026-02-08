from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional


class AudioManager:
    """Gerencia efeitos sonoros e música de fundo com fallback silencioso."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent / "assets" / "audio"
        self._pygame = None
        self._enabled = False
        self._warned = False
        self._sfx_cache: Dict[str, object] = {}

        try:
            import pygame  # type: ignore

            pygame.mixer.init()
            self._pygame = pygame
            self._enabled = True
        except Exception:
            self._enabled = False

    def _resolve_audio(self, filename: str) -> Optional[Path]:
        path = self.base_dir / filename
        if path.exists():
            return path
        if not self._warned:
            print(
                "[Audio] Desativado: dependência ausente ou arquivo de áudio não encontrado em "
                f"{self.base_dir}."
            )
            self._warned = True
        return None

    def play_sfx(self, filename: str) -> None:
        if not self._enabled or not self._pygame:
            return

        audio_path = self._resolve_audio(filename)
        if not audio_path:
            return

        key = str(audio_path)
        sound = self._sfx_cache.get(key)
        if sound is None:
            sound = self._pygame.mixer.Sound(key)
            self._sfx_cache[key] = sound
        sound.play()

    def start_bgm(self, filename: str = "background_music.ogg") -> None:
        if not self._enabled or not self._pygame:
            return

        audio_path = self._resolve_audio(filename)
        if not audio_path:
            return

        self._pygame.mixer.music.load(str(audio_path))
        self._pygame.mixer.music.play(-1)

    def stop_bgm(self) -> None:
        if not self._enabled or not self._pygame:
            return
        self._pygame.mixer.music.stop()


audio_manager = AudioManager()
