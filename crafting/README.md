# Crafting de Varas (modular)

Cada receita de crafting fica em uma pasta com um arquivo JSON proprio:

- `crafting/<craft_id>/<craft_id>.json`

Isso permite adicionar ou ajustar receitas sem mexer no codigo.

## Estrutura basica

```json
{
  "id": "placeholder_vara_brilhante",
  "rod_name": "Vara Brilhante",
  "name": "Receita Placeholder",
  "description": "Receita temporaria usada para validar fluxo.",
  "starts_visible": false,
  "unlock": {
    "mode": "all",
    "requirements": [
      { "type": "level", "level": 8 },
      { "type": "bestiary_percent", "pool_name": "Lagoa Tranquila", "percent": 100 }
    ]
  },
  "craft": {
    "requirements": [
      { "type": "fish", "fish_name": "Lambari", "count": 1 },
      { "type": "money", "amount": 25 }
    ]
  }
}
```

## Tipos de requisito de desbloqueio (`unlock.requirements`)

| Tipo | Campos | O que faz |
|------|--------|-----------|
| `level` | `level` | Exige nivel minimo do jogador. |
| `bestiary_percent` | `percent`, `pool_name?` | Exige % do bestiario global ou de uma pool. |
| `find_fish` | `fish_name`, `count` | Exige encontrar peixe (captura ou appraise). |
| `` | `mutation_name`, `count` | Exige encontrar mutacao (captura ou appraise). |
| `unlock_pool` | `pool_name` | Exige pool desbloqueada. |
| `unlock_quest` | `mission_id`, `state?` | Exige missao em estado `unlocked`, `completed` ou `claimed`. |
| `time_played` | `seconds`/`minutes`/`hours` | Exige tempo total de jogo. |
| `unlock_rod` | `rod_name` | Exige vara desbloqueada. |

## Modo de desbloqueio (`unlock.mode`)

- `all`: todos os requisitos devem ser verdadeiros.
- `any`: basta um requisito verdadeiro.

## Tipos de requisito de crafting (`craft.requirements`)

| Tipo | Campos | O que faz |
|------|--------|-----------|
| `fish` | `fish_name?`, `count` | Entregar peixe(s) do inventario (consome os itens). |
| `mutation` | `mutation_name?`, `count` | Entregar peixe(s) com mutacao (consome os itens). |
| `fish_with_mutation` | `fish_name?`, `mutation_name?`, `count` | Entregar peixe com mutacao especifica (consome os itens). |
| `money` | `amount` | Pagar valor da receita (incremental). |
| `level` | `level` | Exige nivel minimo (nao consome nada). |

## Comportamento no jogo

- O menu de crafting fica dentro do Mercado.
- Gate global do menu: nivel >= 8.
- Gate global do menu: 100% do bestiario de peixes em pelo menos uma pool.
- Receitas desbloqueadas aparecem no menu e notificam uma vez: `Nova receita desbloqueada: <nome da vara>`.
- Entrega de peixe e pagamento de dinheiro sao incrementais.
- Quando todos os requisitos de crafting estao completos, `Criar vara` adiciona a vara em `owned_rods` e `unlocked_rods`.
- A receita vai para estado de `crafted` e sai da lista pendente.

## Persistencia

O save guarda:

- `crafting_state`: `unlocked`, `crafted`, `announced`.
- `crafting_progress`: progresso de `find_*`, entregas por receita, dinheiro pago por receita.

## Dicas

- `rod_name` precisa existir em `rods/*.json`, senao a receita e ignorada.
- IDs devem ser curtos e estaveis para manter compatibilidade com saves.
- Campos opcionais como `fish_name` e `mutation_name` funcionam como filtro: ausente = aceita qualquer um naquele tipo.
