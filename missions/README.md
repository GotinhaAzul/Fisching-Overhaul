# Missões (modulares)

Cada missão fica em uma pasta com um `mission.json`. Isso facilita adicionar, remover ou ajustar requisitos/recompensas sem mexer no código.

## Estrutura básica

```json
{
  "id": "minha_missao",
  "name": "Minha Missão",
  "description": "Descrição curta.",
  "starts_unlocked": false,
  "requirements": [
    { "type": "catch_fish", "count": 3 }
  ],
  "rewards": [
    { "type": "money", "amount": 50 }
  ]
}
```

## Tipos de requisitos

| Tipo | Campos | O que faz |
|------|--------|-----------|
| `earn_money` | `amount` | Total de dinheiro acumulado (ganho). |
| `spend_money` | `amount` | Total de dinheiro gasto. |
| `level` | `level` | Alcançar um nível mínimo. |
| `catch_fish` | `count`, `fish_name?` | Capturar peixes (geral ou específico). |
| `deliver_fish` | `count`, `fish_name?` | Entregar peixes para missão (geral ou específico). |
| `sell_fish` | `count`, `fish_name?` | Vender peixes no mercado (geral ou específico). |
| `catch_mutation` | `count`, `mutation_name?` | Capturar peixes com mutação (geral ou específica). |
| `deliver_mutation` | `count`, `mutation_name?` | Entregar peixes com mutação para missão. |
| `catch_fish_with_mutation` | `count`, `fish_name?` | Capturar peixe com mutação. |
| `deliver_fish_with_mutation` | `count`, `fish_name?` | Entregar peixe com mutação para missão. |
| `play_time` | `seconds`/`minutes`/`hours` | Tempo total de jogo. |
| `missions_completed` | `count` | Quantidade de missões concluídas. |
| `bestiary_percent` | `percent` | % do bestiário completo. |
| `bestiary_pool_percent` | `pool_name`, `percent` | % de uma pool específica. |

## Tipos de recompensa

| Tipo | Campos | O que faz |
|------|--------|-----------|
| `money` | `amount` | Adiciona dinheiro. |
| `xp` | `amount` | Adiciona XP. |
| `fish` | `fish_name`, `count?`, `kg?` | Adiciona peixe(s) ao inventário. |
| `unlock_rods` | `rod_names` | Libera varas para compra no mercado. |
| `unlock_pools` | `pool_names` | Libera pools para seleção. |
| `unlock_missions` | `mission_ids` | Libera novas missões. |

## Dicas

- `starts_unlocked: true` indica que a missão começa disponível.
- `fish_name`, `mutation_name` e `pool_name` devem bater exatamente com os nomes dos arquivos cadastrados.
- Use nomes curtos no `id` para facilitar dependências (ex.: desbloquear outras missões).
