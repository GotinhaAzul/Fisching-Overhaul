from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

from utils.baits import BaitCrateDefinition, BaitDefinition
from utils.crafting import (
    CraftingDefinition,
    CraftingProgress,
    CraftingState,
    apply_craft_submission,
    count_inventory_fish,
    count_inventory_mutations,
    deliver_inventory_entry_for_craft,
    format_crafting_requirement,
    get_craft_deliverable_indexes,
    has_any_pool_bestiary_full_completion,
    is_craft_ready,
    pay_craft_requirement,
    required_money_for_craft,
    update_crafting_unlocks,
)
from utils.dialogue import get_market_line
from utils.inventory import InventoryEntry, calculate_entry_value
from utils.levels import apply_xp_gain
from utils.mutations import Mutation, choose_mutation, filter_mutations_for_rod
from utils.rods import Rod
from utils.ui import clear_screen, print_spaced_lines

if TYPE_CHECKING:
    from utils.pesca import FishProfile, FishingPool


ORDER_ROTATION_SECONDS = 6 * 60
ORDER_MIN_COUNT = 2
ORDER_MAX_COUNT = 7


RARITY_REWARD_MULTIPLIER: Dict[str, float] = {
    "Comum": 1.0,
    "Incomum": 1.2,
    "Raro": 1.5,
    "Epico": 1.9,
}


@dataclass
class PoolMarketOrder:
    pool_name: str
    fish_name: str
    rarity: str
    required_count: int
    reward_money: float
    reward_xp: int
    expires_at: float


def _build_pool_order(pool: "FishingPool", now: float) -> Optional[PoolMarketOrder]:
    eligible_fish = [
        fish for fish in pool.fish_profiles
        if fish.rarity.casefold() != "lendario"
    ]
    if not eligible_fish:
        return None

    fish = random.choice(eligible_fish)
    required_count = random.randint(ORDER_MIN_COUNT, ORDER_MAX_COUNT)
    rarity_multiplier = RARITY_REWARD_MULTIPLIER.get(fish.rarity, 1.0)
    reward_money = fish.base_value * required_count * rarity_multiplier
    reward_xp = max(5, int((required_count * rarity_multiplier) * 8))
    return PoolMarketOrder(
        pool_name=pool.name,
        fish_name=fish.name,
        rarity=fish.rarity,
        required_count=required_count,
        reward_money=reward_money,
        reward_xp=reward_xp,
        expires_at=now + ORDER_ROTATION_SECONDS,
    )


def get_pool_market_order(
    pool: "FishingPool",
    orders_by_pool: Dict[str, PoolMarketOrder],
) -> Optional[PoolMarketOrder]:
    now = time.time()
    order = orders_by_pool.get(pool.name)
    if order and now < order.expires_at:
        return order

    new_order = _build_pool_order(pool, now)
    if not new_order:
        orders_by_pool.pop(pool.name, None)
        return None
    orders_by_pool[pool.name] = new_order
    return new_order


def serialize_pool_market_orders(
    orders_by_pool: Dict[str, PoolMarketOrder],
) -> Dict[str, Dict[str, object]]:
    serialized: Dict[str, Dict[str, object]] = {}
    for pool_name, order in orders_by_pool.items():
        serialized[pool_name] = {
            "fish_name": order.fish_name,
            "rarity": order.rarity,
            "required_count": order.required_count,
            "reward_money": order.reward_money,
            "reward_xp": order.reward_xp,
            "expires_at": order.expires_at,
        }
    return serialized


def restore_pool_market_orders(raw_orders: object) -> Dict[str, PoolMarketOrder]:
    if not isinstance(raw_orders, dict):
        return {}

    restored: Dict[str, PoolMarketOrder] = {}
    for pool_name, raw_order in raw_orders.items():
        if not isinstance(pool_name, str) or not isinstance(raw_order, dict):
            continue
        fish_name = raw_order.get("fish_name")
        rarity = raw_order.get("rarity")
        if not isinstance(fish_name, str) or not fish_name:
            continue
        if not isinstance(rarity, str) or not rarity:
            continue
        try:
            required_count = int(raw_order.get("required_count", 0))
            reward_money = float(raw_order.get("reward_money", 0.0))
            reward_xp = int(raw_order.get("reward_xp", 0))
            expires_at = float(raw_order.get("expires_at", 0.0))
        except (TypeError, ValueError):
            continue
        if required_count <= 0 or reward_money <= 0 or reward_xp < 0:
            continue
        restored[pool_name] = PoolMarketOrder(
            pool_name=pool_name,
            fish_name=fish_name,
            rarity=rarity,
            required_count=required_count,
            reward_money=reward_money,
            reward_xp=reward_xp,
            expires_at=expires_at,
        )
    return restored


def format_currency(value: float) -> str:
    return f"R$ {value:0.2f}"


def format_rod_entry(index: int, rod: Rod) -> str:
    return (
        f"{index}. {rod.name} "
        f"(Sorte: {rod.luck:.0%} | KGMax: {rod.kg_max:g} | "
        f"Controle: {rod.control:+.1f}s) - {format_currency(rod.price)}"
    )


def _craft_requirements_progress(
    definition: CraftingDefinition,
    crafting_progress: CraftingProgress,
    level: int,
) -> tuple[int, int]:
    total = len(definition.craft_requirements)
    done = 0
    for requirement in definition.craft_requirements:
        _, _, _, requirement_done = format_crafting_requirement(
            requirement,
            definition.craft_id,
            crafting_progress,
            level,
        )
        if requirement_done:
            done += 1
    return done, total


def _format_crafting_recipe_status(
    definition: CraftingDefinition,
    crafting_state: CraftingState,
    crafting_progress: CraftingProgress,
    level: int,
) -> str:
    if definition.craft_id in crafting_state.crafted:
        return "[CONCLUIDA]"
    if is_craft_ready(definition, crafting_progress, level):
        return "[PRONTA]"
    done, total = _craft_requirements_progress(definition, crafting_progress, level)
    return f"[EM PROGRESSO {done}/{total}]"


def _show_crafting_recipe_detail(
    definition: CraftingDefinition,
    inventory: List[InventoryEntry],
    balance: float,
    level: int,
    available_rods: Sequence[Rod],
    owned_rods: List[Rod],
    unlocked_rods: set[str],
    crafting_state: CraftingState,
    crafting_progress: CraftingProgress,
    on_money_spent,
    on_inventory_changed: Optional[Callable[[], None]] = None,
) -> float:
    while True:
        clear_screen()
        done_count, total_count = _craft_requirements_progress(
            definition,
            crafting_progress,
            level,
        )
        recipe_status = _format_crafting_recipe_status(
            definition,
            crafting_state,
            crafting_progress,
            level,
        )
        header_lines = [
            f"=== Crafting: {definition.name} ===",
            f"Status: {recipe_status}",
            f"Vara alvo: {definition.rod_name}",
            f"Progresso: {done_count}/{total_count} requisitos concluidos",
        ]
        if definition.description:
            header_lines.insert(1, definition.description)
        print_spaced_lines(header_lines)

        print("")
        print("Requisitos:")
        for requirement in definition.craft_requirements:
            label, current, target, done = format_crafting_requirement(
                requirement,
                definition.craft_id,
                crafting_progress,
                level,
            )
            requirement_status = "OK" if done else "PENDENTE"
            print(f"- {label} ({current}/{target}) [{requirement_status}]")

        deliverable_indexes = get_craft_deliverable_indexes(
            definition,
            crafting_progress,
            inventory,
        )
        money_remaining = required_money_for_craft(definition, crafting_progress)
        can_craft = is_craft_ready(definition, crafting_progress, level)

        action_map: Dict[str, str] = {}
        option_number = 1
        print("\nAcoes:")
        if deliverable_indexes:
            key = str(option_number)
            action_map[key] = "deliver_fish"
            print(f"{key}. Entregar peixe ({len(deliverable_indexes)} elegivel/eis)")
            option_number += 1
        if money_remaining > 0:
            key = str(option_number)
            action_map[key] = "pay_money"
            print(f"{key}. Pagar dinheiro ({format_currency(money_remaining)} pendente)")
            option_number += 1
        if can_craft:
            key = str(option_number)
            action_map[key] = "craft"
            print(f"{key}. Criar vara")
        print("0. Voltar")

        choice = input("Escolha uma opcao: ").strip()
        if choice == "0":
            return balance

        action = action_map.get(choice)
        if not action:
            print("Opcao invalida.")
            input("\nEnter para voltar.")
            continue

        if action == "deliver_fish":
            clear_screen()
            print_spaced_lines([
                "=== Entrega para crafting ===",
                f"Receita: {definition.name}",
                "Peixes elegiveis no inventario:",
            ])
            for index in deliverable_indexes:
                entry = inventory[index - 1]
                mutation_label = f" * {entry.mutation_name}" if entry.mutation_name else ""
                print(
                    f"{index}. {entry.name} ({entry.kg:0.2f}kg){mutation_label} "
                    f"- {format_currency(calculate_entry_value(entry))}"
                )

            selection = input("Digite o numero do peixe: ").strip()
            if not selection.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            selected_index = int(selection)
            delivered = deliver_inventory_entry_for_craft(
                definition,
                crafting_progress,
                inventory,
                selected_index,
            )
            if not delivered:
                print("Peixe nao elegivel para este crafting.")
                input("\nEnter para voltar.")
                continue

            mutation_label = f" * {delivered.mutation_name}" if delivered.mutation_name else ""
            print(
                f"Entrega registrada: {delivered.name} ({delivered.kg:0.2f}kg){mutation_label}"
            )
            if on_inventory_changed:
                on_inventory_changed()
            input("\nEnter para voltar.")
            continue

        if action == "pay_money":
            clear_screen()
            print_spaced_lines([
                "=== Pagamento de crafting ===",
                f"Receita: {definition.name}",
                f"Saldo atual: {format_currency(balance)}",
                f"Valor pendente: {format_currency(money_remaining)}",
            ])
            if balance < money_remaining:
                print("Saldo insuficiente para quitar o valor pendente.")
                input("\nEnter para voltar.")
                continue

            confirm = input("Confirmar pagamento integral? (s/n): ").strip().lower()
            if confirm != "s":
                continue

            paid = pay_craft_requirement(
                definition,
                crafting_progress,
                money_remaining,
            )
            balance -= paid
            if on_money_spent and paid > 0:
                on_money_spent(paid)
            print(f"Pagamento registrado: {format_currency(paid)}")
            input("\nEnter para voltar.")
            continue

        if action == "craft":
            success, message = apply_craft_submission(
                definition,
                crafting_state,
                crafting_progress,
                available_rods,
                owned_rods,
                unlocked_rods,
                level=level,
            )
            print(message)
            input("\nEnter para voltar.")
            if success:
                return balance


def _show_crafting_menu(
    inventory: List[InventoryEntry],
    balance: float,
    level: int,
    available_rods: Sequence[Rod],
    owned_rods: List[Rod],
    unlocked_rods: set[str],
    crafting_definitions: Sequence[CraftingDefinition],
    crafting_state: CraftingState,
    crafting_progress: CraftingProgress,
    on_money_spent,
    refresh_unlocks: Callable[[], None],
    on_inventory_changed: Optional[Callable[[], None]] = None,
) -> float:
    crafting_by_id = {definition.craft_id: definition for definition in crafting_definitions}

    while True:
        refresh_unlocks()
        clear_screen()

        visible_recipes = sorted(
            (
                definition
                for definition in crafting_by_id.values()
                if definition.craft_id in crafting_state.unlocked
                and definition.craft_id not in crafting_state.crafted
            ),
            key=lambda definition: definition.name,
        )
        print_spaced_lines([
            "=== Crafting de varas ===",
            f"Receitas desbloqueadas: {len(visible_recipes)}",
            f"Receitas concluidas: {len(crafting_state.crafted)}",
        ])
        if not visible_recipes:
            print("Nenhuma receita disponivel no momento.")
            input("\nEnter para voltar.")
            return balance

        print("")
        print("Receitas:")
        for index, definition in enumerate(visible_recipes, start=1):
            recipe_status = _format_crafting_recipe_status(
                definition,
                crafting_state,
                crafting_progress,
                level,
            )
            done_count, total_count = _craft_requirements_progress(
                definition,
                crafting_progress,
                level,
            )
            print(f"{index}. {definition.name} {recipe_status} ({done_count}/{total_count})")
        print("0. Voltar")

        choice = input("Escolha uma receita: ").strip()
        if choice == "0":
            return balance
        if not choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            continue

        selected_index = int(choice)
        if not (1 <= selected_index <= len(visible_recipes)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            continue

        selected_recipe = visible_recipes[selected_index - 1]
        balance = _show_crafting_recipe_detail(
            selected_recipe,
            inventory,
            balance,
            level,
            available_rods,
            owned_rods,
            unlocked_rods,
            crafting_state,
            crafting_progress,
            on_money_spent,
            on_inventory_changed,
        )


def show_market(
    inventory: List[InventoryEntry],
    balance: float,
    selected_pool: "FishingPool",
    level: int,
    xp: int,
    available_rods: List[Rod],
    owned_rods: List[Rod],
    fish_by_name: Dict[str, "FishProfile"],
    available_mutations: List[Mutation],
    *,
    equipped_rod: Optional[Rod] = None,
    pools: Optional[Sequence["FishingPool"]] = None,
    discovered_fish: Optional[set[str]] = None,
    mission_state: object = None,
    play_time_seconds: float = 0.0,
    crafting_definitions: Optional[Sequence[CraftingDefinition]] = None,
    crafting_state: Optional[CraftingState] = None,
    crafting_progress: Optional[CraftingProgress] = None,
    bait_crates: Optional[Sequence[BaitCrateDefinition]] = None,
    bait_inventory: Optional[Dict[str, int]] = None,
    bait_by_id: Optional[Dict[str, BaitDefinition]] = None,
    pool_orders: Optional[Dict[str, PoolMarketOrder]] = None,
    unlocked_rods: Optional[set[str]] = None,
    unlocked_pools: Optional[set[str]] = None,
    on_money_earned=None,
    on_money_spent=None,
    on_fish_sold=None,
    on_fish_delivered=None,
    on_appraise_completed: Optional[Callable[[InventoryEntry], Optional[List[str]]]] = None,
) -> tuple[float, int, int]:
    pool_orders = pool_orders if pool_orders is not None else {}
    resolved_pools = list(pools) if pools is not None else []
    resolved_bait_crates = list(bait_crates) if bait_crates is not None else []
    resolved_bait_inventory = bait_inventory if bait_inventory is not None else {}
    resolved_bait_by_id = dict(bait_by_id) if bait_by_id is not None else {}
    for crate in resolved_bait_crates:
        for bait in crate.baits:
            resolved_bait_by_id.setdefault(bait.bait_id, bait)
    resolved_discovered_fish = discovered_fish if discovered_fish is not None else set()
    resolved_unlocked_rods = unlocked_rods if unlocked_rods is not None else set()
    resolved_unlocked_pools = unlocked_pools if unlocked_pools is not None else set()
    normalized_unlocked_pools = {
        pool_name.strip().casefold()
        for pool_name in resolved_unlocked_pools
    }
    selected_pool_id = selected_pool.folder.name.strip().casefold()
    selected_pool_name = selected_pool.name.strip().casefold()
    crafting_notifications: List[str] = []
    inventory_fish_counts_cache: Dict[str, int] = {}
    inventory_mutation_counts_cache: Dict[str, int] = {}
    inventory_fish_counts_dirty = True

    def _appraise_cost(entry: InventoryEntry) -> float:
        return max(1.0, calculate_entry_value(entry) * 0.35)

    def _mark_inventory_fish_counts_dirty() -> None:
        nonlocal inventory_fish_counts_dirty
        inventory_fish_counts_dirty = True

    def _rebuild_inventory_count_caches_if_needed() -> None:
        nonlocal inventory_fish_counts_dirty
        if not inventory_fish_counts_dirty:
            return
        inventory_fish_counts_cache.clear()
        inventory_fish_counts_cache.update(count_inventory_fish(inventory))
        inventory_mutation_counts_cache.clear()
        inventory_mutation_counts_cache.update(count_inventory_mutations(inventory))
        inventory_fish_counts_dirty = False

    def _get_inventory_fish_counts() -> Dict[str, int]:
        _rebuild_inventory_count_caches_if_needed()
        return inventory_fish_counts_cache

    def _get_inventory_mutation_counts() -> Dict[str, int]:
        _rebuild_inventory_count_caches_if_needed()
        return inventory_mutation_counts_cache

    def _refresh_crafting_unlocks() -> None:
        if not crafting_definitions or not crafting_state or not crafting_progress:
            return
        newly_unlocked = update_crafting_unlocks(
            crafting_definitions,
            crafting_state,
            crafting_progress,
            level=level,
            pools=resolved_pools,
            discovered_fish=resolved_discovered_fish,
            unlocked_pools=resolved_unlocked_pools,
            mission_state=mission_state,
            unlocked_rods=resolved_unlocked_rods,
            play_time_seconds=play_time_seconds,
            inventory_fish_counts=_get_inventory_fish_counts(),
            inventory_mutation_counts=_get_inventory_mutation_counts(),
        )
        for definition in newly_unlocked:
            crafting_notifications.append(f"Nova receita desbloqueada: {definition.rod_name}")

    def _crafting_gate_status() -> tuple[bool, str]:
        if not resolved_pools:
            return False, "Crafting indisponivel sem pools carregadas."
        if level < 8:
            return False, "Crafting bloqueado: alcance o nivel 8."
        if not has_any_pool_bestiary_full_completion(resolved_pools, resolved_discovered_fish):
            return False, "Crafting bloqueado: complete 100% do bestiario em ao menos uma pool."
        return True, ""

    def _format_bait_stats(bait: BaitDefinition) -> str:
        return (
            f"Sorte: {bait.luck:+.0%} | KG+: {bait.kg_plus:+g} | "
            f"Controle: {bait.control:+.1f}s"
        )

    def _format_rarity_distribution(crate: BaitCrateDefinition) -> str:
        if not crate.rarity_chances:
            return "Distribuicao: uniforme"
        total_weight = sum(crate.rarity_chances.values())
        if total_weight <= 0:
            return "Distribuicao: uniforme"
        sorted_weights = sorted(
            crate.rarity_chances.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        labels = [
            f"{rarity}:{(weight / total_weight) * 100:0.0f}%"
            for rarity, weight in sorted_weights
        ]
        return "Distribuicao: " + " | ".join(labels)

    def _show_bait_crates_menu(current_balance: float) -> float:
        balance_local = current_balance
        while True:
            clear_screen()
            if not resolved_bait_crates:
                print("Nenhuma caixa de isca disponivel.")
                input("\nEnter para voltar.")
                return balance_local

            print_spaced_lines([
                "=== Caixas de Isca ===",
                f"Saldo atual: {format_currency(balance_local)}",
                "Cada caixa abre com quantidade aleatoria de iscas.",
            ])
            for index, crate in enumerate(resolved_bait_crates, start=1):
                print(
                    f"{index}. {crate.name} - {format_currency(crate.price)} | "
                    f"Roll: {crate.roll_min}-{crate.roll_max} "
                    f"(media {crate.expected_rolls():0.1f})"
                )
                print(f"   {_format_rarity_distribution(crate)}")
                print()
            print("0. Voltar")

            selection = input("Escolha uma caixa: ").strip()
            if selection == "0":
                return balance_local
            if not selection.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                continue

            selected_index = int(selection)
            if not (1 <= selected_index <= len(resolved_bait_crates)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            crate = resolved_bait_crates[selected_index - 1]
            raw_quantity = input("Quantidade de caixas para abrir: ").strip()
            if not raw_quantity.isdigit():
                print("Quantidade invalida.")
                input("\nEnter para voltar.")
                continue
            crate_quantity = int(raw_quantity)
            if crate_quantity <= 0:
                print("A quantidade deve ser maior que zero.")
                input("\nEnter para voltar.")
                continue

            total_cost = crate.price * crate_quantity
            if balance_local < total_cost:
                print("Saldo insuficiente.")
                input("\nEnter para voltar.")
                continue

            confirm = input(
                f"Confirmar compra de {crate_quantity}x {crate.name} "
                f"por {format_currency(total_cost)}? (s/n): "
            ).strip().lower()
            if confirm != "s":
                continue

            balance_local -= total_cost
            if on_money_spent:
                on_money_spent(total_cost)

            dropped_by_bait_id: Dict[str, int] = {}
            for _ in range(crate_quantity):
                for dropped_bait in crate.open_crate():
                    dropped_by_bait_id[dropped_bait.bait_id] = (
                        dropped_by_bait_id.get(dropped_bait.bait_id, 0) + 1
                    )
                    resolved_bait_inventory[dropped_bait.bait_id] = (
                        resolved_bait_inventory.get(dropped_bait.bait_id, 0) + 1
                    )

            if not dropped_by_bait_id:
                print("Nenhuma isca foi recebida desta abertura.")
                input("\nEnter para voltar.")
                continue

            clear_screen()
            print_spaced_lines([
                "=== Abertura concluida ===",
                f"Caixa: {crate.name}",
                f"Quantidade: {crate_quantity}",
                f"Custo: {format_currency(total_cost)}",
            ])
            print("Iscas obtidas:")
            for bait_id, quantity in sorted(
                dropped_by_bait_id.items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                bait = resolved_bait_by_id.get(bait_id)
                bait_name = bait.name if bait else bait_id
                total_owned = resolved_bait_inventory.get(bait_id, 0)
                rarity_label = f"[{bait.rarity}] " if bait else ""
                stats_label = _format_bait_stats(bait) if bait else ""
                print(
                    f"- {rarity_label}{bait_name} x{quantity} "
                    f"(total: {total_owned})"
                )
                if stats_label:
                    print(f"  {stats_label}")
            input("\nEnter para continuar.")

    def _handle_sell_action(current_balance: float) -> float:
        balance_local = current_balance
        clear_screen()
        if not inventory:
            print("Inventario vazio.")
            input("\nEnter para voltar.")
            return balance_local

        print_spaced_lines([
            "Escolha como vender:",
            "1. Vender peixe individual",
            "2. Vender inventario inteiro",
            "0. Voltar",
        ])

        sell_choice = input("Escolha uma opcao: ").strip()
        if sell_choice == "0":
            return balance_local

        if sell_choice == "1":
            clear_screen()
            print_spaced_lines(["Escolha o peixe para vender:"])
            for index, entry in enumerate(inventory, start=1):
                value = calculate_entry_value(entry)
                mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
                print(
                    f"{index}. {entry.name} "
                    f"({entry.kg:0.2f}kg){mutation_label} - {format_currency(value)}"
                )

            selection = input("Digite o numero do peixe: ").strip()
            if not selection.isdigit():
                print("Entrada invalida.")
                input("\nEnter para voltar.")
                return balance_local

            selected_index = int(selection)
            if not (1 <= selected_index <= len(inventory)):
                print("Numero fora do intervalo.")
                input("\nEnter para voltar.")
                return balance_local

            entry = inventory.pop(selected_index - 1)
            _mark_inventory_fish_counts_dirty()
            value = calculate_entry_value(entry)
            balance_local += value
            if on_money_earned:
                on_money_earned(value)
            if on_fish_sold:
                on_fish_sold(entry)
            if on_fish_delivered:
                on_fish_delivered(entry)
            mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
            print(
                f"Vendeu {entry.name} ({entry.kg:0.2f}kg){mutation_label} "
                f"por {format_currency(value)}."
            )
            input("\nEnter para voltar.")
            return balance_local

        if sell_choice == "2":
            clear_screen()
            total = sum(calculate_entry_value(entry) for entry in inventory)
            if on_fish_sold or on_fish_delivered:
                for entry in inventory:
                    if on_fish_sold:
                        on_fish_sold(entry)
                    if on_fish_delivered:
                        on_fish_delivered(entry)
            inventory.clear()
            _mark_inventory_fish_counts_dirty()
            balance_local += total
            if on_money_earned:
                on_money_earned(total)
            print(f"Inventario vendido por {format_currency(total)}.")
            input("\nEnter para voltar.")
            return balance_local

        print("Opcao invalida.")
        input("\nEnter para voltar.")
        return balance_local

    def _handle_buy_rod_action(current_balance: float) -> float:
        balance_local = current_balance
        clear_screen()
        owned_rod_names = {rod.name for rod in owned_rods}
        rods_for_sale = [
            rod
            for rod in available_rods
            if rod.name not in owned_rod_names
            and (
                unlocked_rods is None
                or rod.name in resolved_unlocked_rods
                or (
                    bool(rod.unlocks_with_pool)
                    and rod.unlocks_with_pool.strip().casefold()
                    in {selected_pool_id, selected_pool_name}
                    and (
                        selected_pool.name in resolved_unlocked_pools
                        or selected_pool_id in normalized_unlocked_pools
                        or selected_pool_name in normalized_unlocked_pools
                    )
                )
            )
        ]
        if not rods_for_sale:
            print("Nenhuma vara disponivel para compra.")
            input("\nEnter para voltar.")
            return balance_local

        print_spaced_lines(["Varas disponiveis:"])
        for index, rod in enumerate(rods_for_sale, start=1):
            print(format_rod_entry(index, rod))
            print(f"   {rod.description}")
            print()

        selection = input("Digite o numero da vara: ").strip()
        if not selection.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            return balance_local

        selected_index = int(selection)
        if not (1 <= selected_index <= len(rods_for_sale)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            return balance_local

        rod = rods_for_sale[selected_index - 1]
        if balance_local < rod.price:
            print("Saldo insuficiente.")
            input("\nEnter para voltar.")
            return balance_local

        balance_local -= rod.price
        if on_money_spent:
            on_money_spent(rod.price)
        owned_rods.append(rod)
        print(f"Comprou {rod.name} por {format_currency(rod.price)}.")
        input("\nEnter para voltar.")
        return balance_local

    def _handle_order_action(
        current_balance: float,
        current_level: int,
        current_xp: int,
    ) -> tuple[float, int, int]:
        balance_local = current_balance
        level_local = current_level
        xp_local = current_xp
        clear_screen()
        order = get_pool_market_order(selected_pool, pool_orders)
        if not order:
            print("Nao ha pedido disponivel para esta pool agora.")
            input("\nEnter para voltar.")
            return balance_local, level_local, xp_local

        matching_entries = [
            entry
            for entry in inventory
            if entry.name == order.fish_name
        ]
        print_spaced_lines([
            "📦 Pedido Atual ",
            f"Pool: {order.pool_name}",
            f"Solicitacao: {order.required_count}x {order.fish_name} [{order.rarity}]",
            f"Disponivel no inventario: {len(matching_entries)}",
            f"Recompensa: {format_currency(order.reward_money)} + {order.reward_xp} XP",
        ])

        if len(matching_entries) < order.required_count:
            print("Voce ainda nao tem peixes suficientes para cumprir o pedido.")
            input("\nEnter para voltar.")
            return balance_local, level_local, xp_local

        confirm = input("Entregar agora? (s/n): ").strip().lower()
        if confirm != "s":
            return balance_local, level_local, xp_local

        delivered = 0
        remaining_inventory: List[InventoryEntry] = []
        for entry in inventory:
            if entry.name == order.fish_name and delivered < order.required_count:
                delivered += 1
                if on_fish_sold:
                    on_fish_sold(entry)
                if on_fish_delivered:
                    on_fish_delivered(entry)
                continue
            remaining_inventory.append(entry)

        inventory[:] = remaining_inventory
        _mark_inventory_fish_counts_dirty()
        balance_local += order.reward_money
        level_local, xp_local, level_ups = apply_xp_gain(level_local, xp_local, order.reward_xp)
        if on_money_earned:
            on_money_earned(order.reward_money)
        print(
            f"Pedido entregue! Voce recebeu {format_currency(order.reward_money)} "
            f"e {order.reward_xp} XP."
        )
        if level_ups:
            print(f"⬆️ Voce subiu {level_ups} nivel(is)!")
        pool_orders.pop(selected_pool.name, None)
        input("\nEnter para voltar.")
        return balance_local, level_local, xp_local

    def _handle_appraise_action(current_balance: float) -> float:
        balance_local = current_balance
        clear_screen()
        if not inventory:
            print("Inventario vazio.")
            input("\nEnter para voltar.")
            return balance_local

        print_spaced_lines([
            "🔎 Appraise",
            "Escolha um peixe para rerolar KG e mutacao.",
            "Que a sorte esteja com voce!",
        ])
        for index, entry in enumerate(inventory, start=1):
            value = calculate_entry_value(entry)
            cost = _appraise_cost(entry)
            mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
            print(
                f"{index}. {entry.name} ({entry.kg:0.2f}kg){mutation_label} "
                f"- Valor: {format_currency(value)} | Custo: {format_currency(cost)}"
            )

        selection = input("Digite o numero do peixe: ").strip()
        if not selection.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            return balance_local

        selected_index = int(selection)
        if not (1 <= selected_index <= len(inventory)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            return balance_local

        entry = inventory[selected_index - 1]
        profile = fish_by_name.get(entry.name)
        if not profile:
            print("Esse peixe nao pode ser avaliado agora.")
            input("\nEnter para voltar.")
            return balance_local

        cost = _appraise_cost(entry)
        if balance_local < cost:
            print("Saldo insuficiente para appraise.")
            input("\nEnter para voltar.")
            return balance_local

        old_kg = entry.kg
        old_mutation = entry.mutation_name
        old_value = calculate_entry_value(entry)

        confirm = input(
            f"Cobrar {format_currency(cost)} para rerolar {entry.name}. Confirmar? (s/n): "
        ).strip().lower()
        if confirm != "s":
            return balance_local

        balance_local -= cost
        if on_money_spent:
            on_money_spent(cost)

        entry.kg = random.uniform(profile.kg_min, profile.kg_max)
        appraise_mutations = (
            filter_mutations_for_rod(available_mutations, equipped_rod.name)
            if equipped_rod is not None
            else list(available_mutations)
        )
        mutation = choose_mutation(appraise_mutations)
        entry.mutation_name = mutation.name if mutation else None
        entry.mutation_xp_multiplier = mutation.xp_multiplier if mutation else 1.0
        entry.mutation_gold_multiplier = mutation.gold_multiplier if mutation else 1.0
        new_value = calculate_entry_value(entry)

        old_mutation_label = old_mutation if old_mutation else "Sem mutacao"
        new_mutation_label = entry.mutation_name if entry.mutation_name else "Sem mutacao"
        value_delta = new_value - old_value
        print_spaced_lines([
            "✅ Appraise concluido!",
            f"KG: {old_kg:0.2f} -> {entry.kg:0.2f}",
            f"Mutacao: {old_mutation_label} -> {new_mutation_label}",
            (
                f"Valor estimado: {format_currency(old_value)} -> {format_currency(new_value)} "
                f"({value_delta:+.2f})"
            ),
        ])

        if on_appraise_completed:
            notes = on_appraise_completed(entry)
            if notes:
                print("")
                for note in notes:
                    print(note)
        _refresh_crafting_unlocks()

        input("\nEnter para voltar.")
        return balance_local

    def _handle_crafting_action(
        current_balance: float,
        *,
        crafting_gate_open: bool,
        crafting_gate_reason: str,
    ) -> float:
        if not (crafting_definitions and crafting_state and crafting_progress):
            print("Sistema de crafting indisponivel no momento.")
            input("\nEnter para voltar.")
            return current_balance
        if not crafting_gate_open:
            print(crafting_gate_reason)
            input("\nEnter para voltar.")
            return current_balance
        return _show_crafting_menu(
            inventory,
            current_balance,
            level,
            available_rods,
            owned_rods,
            resolved_unlocked_rods,
            crafting_definitions,
            crafting_state,
            crafting_progress,
            on_money_spent,
            _refresh_crafting_unlocks,
            _mark_inventory_fish_counts_dirty,
        )

    while True:
        _refresh_crafting_unlocks()
        clear_screen()
        order = get_pool_market_order(selected_pool, pool_orders)
        order_line = "3. Pedido atual"
        if order:
            time_left_s = max(0, int(order.expires_at - time.time()))
            minutes_left = time_left_s // 60
            seconds_left = time_left_s % 60
            order_line = (
                "3. Pedido atual "
                f"({order.required_count}x {order.fish_name} [{order.rarity}] | "
                f"{minutes_left:02d}:{seconds_left:02d})"
            )

        crafting_gate_open, crafting_gate_reason = _crafting_gate_status()
        crafting_line = "6. Crafting de varas"
        if not (crafting_definitions and crafting_state and crafting_progress):
            crafting_line += " (indisponivel)"
        elif not crafting_gate_open:
            crafting_line += " (bloqueado)"

        lines = [
            "🛒 === Mercado ===",
            get_market_line(),
            f"Pool atual: {selected_pool.name}",
            f"Dinheiro: {format_currency(balance)}",
        ]
        if crafting_notifications:
            lines.extend(f"🔔 {note}" for note in crafting_notifications)
            crafting_notifications.clear()
        lines.extend(
            [
                "1. Vender peixe",
                "2. Comprar vara",
                order_line,
                "4. Appraise - rerolar kg + mutacao",
                "5. Caixas de isca",
                crafting_line,
                "0. Voltar",
            ]
        )
        print_spaced_lines(lines)

        choice = input("Escolha uma opcao: ").strip()
        if choice == "0":
            return balance, level, xp

        if choice == "1":
            balance = _handle_sell_action(balance)
            continue

        if choice == "2":
            balance = _handle_buy_rod_action(balance)
            continue

        if choice == "3":
            balance, level, xp = _handle_order_action(balance, level, xp)
            continue

        if choice == "4":
            balance = _handle_appraise_action(balance)
            continue

        if choice == "5":
            balance = _show_bait_crates_menu(balance)
            continue

        if choice == "6":
            balance = _handle_crafting_action(
                balance,
                crafting_gate_open=crafting_gate_open,
                crafting_gate_reason=crafting_gate_reason,
            )
            continue

        print("Opcao invalida.")
        input("\nEnter para voltar.")
