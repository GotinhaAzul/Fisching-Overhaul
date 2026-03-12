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

Versao atual: `1.4`

### Update 1.4: Skies of Rain

- Nova pool desbloqueavel: `Celestia`, uma ilha flutuante acima das nuvens com `16` peixes exclusivos.
- Nova missao de desbloqueio: `Alem das nuvens.`, exigindo nivel `15` e entregas de `Carpa Eterea` e `Peixe Farol`.
- Nova vara tematizada: `Vara das Nuvens`, liberada junto com `Celestia`.
- Nova mutacao exclusiva: `Nuvem`, com bonus de `1.2x XP` e `1.3x gold` para capturas com a `Vara das Nuvens`.
- Novo evento global: `Cardume Celestial`, trazendo peixes raros para qualquer pool ativa por tempo limitado.
- Novo sistema de clima com rotacao automatica e suporte a configuracao por JSON.
- Climas iniciais incluidos:
  - `Limpo`
  - `Chuvoso`
  - `Neblina`
  - `Ventania`
- Os modificadores de clima afetam a gameplay em tempo real com bonus de XP, sorte e controle.
- Suite de testes expandida para cobrir o carregamento de clima, rotacao, notificacoes e modificadores.

## Estrutura do projeto

- `start_game.py`: entrada principal do jogo.
- `start_game_dev.py`: inicializacao com `dev_mode=True`.
- `utils/`: logica de runtime, UI, mercado, crafting, inventario, clima, save, eventos, hunts e pesca.
- `pools/`, `rods/`, `baits/`, `mutations/`, `missions/`, `events/`, `hunts/`, `crafting/`, `weather/`: conteudo data-driven.
- `cosmetics_catalog/`, `bestiary_rewards/`: catalogos e recompensas de progressao.
- `tests/`: testes de caracterizacao.

