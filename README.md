# Fisching-Overhaul

Simple Fisching text game overhaul.

Focused on being very easily expandable

## Como executar

```bash
pip install colorama pynput
python main.py
```

## Áudios (opcional)

Para habilitar efeitos sonoros e música de fundo, instale também:

```bash
pip install pygame
```

Depois, adicione arquivos em `assets/audio/` com estes nomes:

- `background_music.ogg`
- `fish_catch_success.ogg`
- `sell_fish.ogg`
- `buy_rod.ogg`
- `appraise.ogg`

Se os arquivos (ou o `pygame`) não estiverem disponíveis, o jogo continua rodando sem áudio.
