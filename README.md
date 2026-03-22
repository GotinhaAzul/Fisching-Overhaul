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

Versao atual: `1.6`

### Update 1.6: Devs'n Secrets

- Varas agora podem modificar a chance de pescar peixes `shiny`.
- Completar bestiarios pode agora recompensar peixes.
- 3 novas varas adicionadas:
  - `Azul Lamina`
  - `Serenidade`
  - `Maos`
- 2 novas mutacoes:
  - `Sereno` (exclusiva da `Serenidade` e da `Hollow Dusk`).
  - `Caotico`
- Alem dos cristais da angra, uma passagem se abre para uma... cafeteria? Talvez completar o seu bestiario te de um *Codigo* para entrar na cafeteria. (Digite o codigo na aba de selecao de Pool)
- Bug fixes and changes:
  - A habilidade `Pierce` nao deve mais fazer o jogador perder a sequencia; cada erro corrigido conta como uma tecla acertada.
  - `Frenzy` estava forte demais — tempo reduzido, tornando sequencias longas mais dificeis.
  - Adicionada paginação no Appraise
  - Adicionada paginação na venda de peixe individual
  - Banshee Ígnea da missão do Prologo agora é entregável, permitindo acesso a Fossa das Marianas. Este bug foi causado por um erro no nome do peixe. (Desculpa por esse bug...)

## Previous Update Notes

### Update 1.5: Skies of Rain

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

### Update 1.4: Luminosity

- 2 novas pools desbloqueaveis:
  - `Caverna Luminosa`, liberada entregando um Surubim com mutacao Brilhante apos 70% do bestiario de Profundezas Desoladas.
  - `Caverna Carmesim`, liberada entregando um Dragao Azul com mutacao Carmesim apos 70% do bestiario de Caverna Luminosa.
- 2 novas missoes de desbloqueio: `A Fenda Luminosa` e `Alem da Luz, o Vermelho`.
- 3 novas hunts:
  - `O Chamado Azul` - Dragao Azul (Lendario) na Caverna Luminosa.
  - `A Chama Carmesim` - Dragao Carmesim (Lendario) na Caverna Carmesim.
  - `O Ultimo Mito` - Dragao Etereo (Mitico) na Caverna Carmesim, hunt rarissima.
- 3 novas mutacoes:
  - `Carmesim` (0.16%, universal ultra-rara, 1.5x XP/Gold).
  - `Prometido` (10%, exclusiva da Promessa Luminescente, 1.4x XP / 1.6x Gold).
  - `Prometido` (15%, exclusiva da Ruina Prometida, 1.4x XP / 1.6x Gold).
- 2 novas varas:
  - `Promessa Luminescente` - Sorte/Controle/KG medios, desbloqueada com Caverna Luminosa.
  - `Ruina Prometida` - Sorte alta, KG alto, Controle baixo; craftada com Dragao Carmesim + itens raros.
- 18 novos peixes distribuidos entre as duas cavernas.

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

### Update 1.2: A fossa das Marianas

- Uma nova questline completa explorando as profundezas do oceano, novos peixes desafiadores aguardam.
- Nova raridade adicionada: `Mitico`.
- `6` novas varas adicionadas.
- Tem um pinguim agora em `snowcap`.
- Rework na UI da pesca + melhorias no inventario.
- `pynput` adicionado a paginas de navegacao.
- Bug fixes:
  - Algumas melhorias de performance.

## Estrutura do projeto

- `start_game.py`: entrada principal do jogo.
- `start_game_dev.py`: inicializacao com `dev_mode=True`.
- `utils/`: logica de runtime, UI, mercado, crafting, inventario, clima, save, eventos, hunts e pesca.
- `pools/`, `rods/`, `baits/`, `mutations/`, `missions/`, `events/`, `hunts/`, `crafting/`, `weather/`: conteudo data-driven.
- `cosmetics_catalog/`, `bestiary_rewards/`: catalogos e recompensas de progressao.
- `tests/`: testes de caracterizacao.

