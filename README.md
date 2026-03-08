# Fisching-Overhaul

Simple Fisching text game overhaul.

Focused on being easily expandable, with most gameplay content driven by JSON files.

Basicamente, um jogo de pesca em texto feito para crescer com novas pools, varas, mutacoes, eventos, hunts e missoes.

Aperte as teclas na sequencia correta e pesque peixes.

## Como executar

```bash
python3 -m pip install -e .
fisching
```

Ou, sem instalar o comando:

```bash
python3 start_game.py
```

Modo de desenvolvimento:

```bash
python3 start_game_dev.py
```

Rodar testes:

```bash
python3 -m pytest -q
```

## Versao Atual

Versao atual: `1.3`

### Update 1.3: Rods and the Forbidden

- Nova pool desbloqueavel: `O Jardim`, liberada pela missao `Raizes Submersas`.
- Nova questline `Densa Mata` com Prologo + Partes 1, 2 e 3.
- Nova pool de endgame: `Templo de Micelio`, com 9 peixes e bestiario oculto ate o desbloqueio.
- Nova hunt: `O Guardiao`, com `Mossjaw` e `Awakened Mossjaw`.
- Nova mutacao: `Incinerado`, exclusiva da vara `Magnasas`.
- 5 novas varas de alto nivel:
  - `Trinity`
  - `Perforatio` com habilidade `Pierce`
  - `Frenesis` com habilidade `Frenzy`
  - `Midas` com habilidade `Greed`
  - `Magnasas`
- Suporte de gameplay para as novas habilidades de vara ja integrado ao minigame de pesca.

## Estrutura do projeto

- `start_game.py`: entrada principal do jogo.
- `start_game_dev.py`: inicializacao com `dev_mode=True`.
- `utils/`: logica de runtime, UI, mercado, crafting, inventario, save, eventos, hunts e pesca.
- `pools/`, `rods/`, `baits/`, `mutations/`, `missions/`, `events/`, `hunts/`, `crafting/`: conteudo data-driven.
- `tests/`: testes de caracterizacao.

