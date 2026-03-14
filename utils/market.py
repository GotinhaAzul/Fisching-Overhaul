from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

from colorama import Fore, Style

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
from utils.shiny import ShinyConfig, roll_shiny_on_appraise
from utils.menu_input import read_menu_choice
from utils.modern_ui import MenuOption, get_ui_symbol, print_menu_panel
from utils.mutations import Mutation, choose_mutation, filter_mutations_for_rod
from utils.rods import Rod
from utils.rod_upgrades import (
    UPGRADEABLE_STATS,
    RodUpgradeState,
    UpgradeRequirement,
    apply_stat_bonus,
    calculate_upgrade_bonus,
    compute_upgrade_cost,
    format_rod_stats,
    format_upgrade_stat_value,
    format_upgrade_summary,
    generate_fish_requirements,
    get_effective_rod,
)
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
                    f"- {format_currency(_calc_value(entry))}"
                )

            print(f"\n[T] Entregar todos ({len(deliverable_indexes)} peixe(s))")

            selection = input("Digite o numero do peixe (ou T para todos): ").strip()

            if selection.lower() == "t":
                delivered_entries: list[InventoryEntry] = []
                while True:
                    current_indexes = get_craft_deliverable_indexes(
                        definition, crafting_progress, inventory,
                    )
                    if not current_indexes:
                        break
                    delivered = deliver_inventory_entry_for_craft(
                        definition, crafting_progress, inventory, current_indexes[0],
                    )
                    if not delivered:
                        break
                    delivered_entries.append(delivered)
                if delivered_entries:
                    for d in delivered_entries:
                        mutation_label = f" * {d.mutation_name}" if d.mutation_name else ""
                        print(f"Entregue: {d.name} ({d.kg:0.2f}kg){mutation_label}")
                    print(f"\n{len(delivered_entries)} peixe(s) entregue(s)!")
                else:
                    print("Nenhum peixe entregue.")
                if on_inventory_changed:
                    on_inventory_changed()
                input("\nEnter para voltar.")
                continue

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
    rod_upgrade_state: Optional[RodUpgradeState] = None,
    on_money_earned=None,
    on_money_spent=None,
    on_fish_sold=None,
    on_fish_delivered=None,
    on_appraise_completed: Optional[Callable[[InventoryEntry], Optional[List[str]]]] = None,
    shiny_config: Optional[ShinyConfig] = None,
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
    resolved_rod_upgrade_state = (
        rod_upgrade_state
        if rod_upgrade_state is not None
        else RodUpgradeState()
    )
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
    _shiny_mult = shiny_config.value_multiplier if shiny_config else 1.55

    def _calc_value(entry: InventoryEntry) -> float:
        return calculate_entry_value(entry, shiny_multiplier=_shiny_mult)

    def _appraise_cost(entry: InventoryEntry) -> float:
        return max(1.0, _calc_value(entry) * 0.35)

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

    def _is_upgrade_pool_unlocked(pool: "FishingPool") -> bool:
        if not normalized_unlocked_pools:
            return (
                pool.name.strip().casefold() == selected_pool_name
                or pool.folder.name.strip().casefold() == selected_pool_id
            )
        return (
            pool.name.strip().casefold() in normalized_unlocked_pools
            or pool.folder.name.strip().casefold() in normalized_unlocked_pools
        )

    def _get_upgrade_pool_fish() -> List["FishProfile"]:
        source_pools = resolved_pools or [selected_pool]
        seen_fish_names: set[str] = set()
        available_fish: List["FishProfile"] = []
        for pool in source_pools:
            if not _is_upgrade_pool_unlocked(pool):
                continue
            if getattr(pool, "hidden_from_pool_selection", False):
                continue
            for fish in pool.fish_profiles:
                fish_name = getattr(fish, "name", "")
                if not fish_name or fish_name in seen_fish_names:
                    continue
                seen_fish_names.add(fish_name)
                available_fish.append(fish)
        return available_fish

    def _upgrade_gate_status() -> tuple[bool, str]:
        if level < 20:
            return False, "Melhoria bloqueada: alcance o nivel 20."
        if not _get_upgrade_pool_fish():
            return False, "Melhoria indisponivel: nao ha peixes nas pools desbloqueadas."
        return True, ""

    def _build_upgrade_requirement_lines(
        requirements: Sequence[UpgradeRequirement],
    ) -> tuple[List[str], bool]:
        inventory_counts: Dict[str, int] = {}
        for entry in inventory:
            if entry.is_unsellable:
                continue
            inventory_counts[entry.name] = inventory_counts.get(entry.name, 0) + 1
        all_requirements_met = True
        lines: List[str] = []
        for requirement in requirements:
            owned = inventory_counts.get(requirement.fish_name, 0)
            enough = owned >= requirement.count
            if not enough:
                all_requirements_met = False
            marker = "[green]✓[/green]" if enough else "[red]✗[/red]"
            owned_style = "green" if enough else "red"
            lines.append(
                f"{marker} {requirement.count}x {requirement.fish_name} "
                f"({requirement.rarity}) - voce tem: [{owned_style}]{owned}[/]"
            )
        return lines, all_requirements_met

    def _consume_upgrade_requirements(
        requirements: Sequence[UpgradeRequirement],
    ) -> None:
        remaining_by_name: Dict[str, int] = {}
        for requirement in requirements:
            remaining_by_name[requirement.fish_name] = (
                remaining_by_name.get(requirement.fish_name, 0) + requirement.count
            )

        index = 0
        while index < len(inventory):
            entry = inventory[index]
            if entry.is_unsellable:
                index += 1
                continue
            remaining = remaining_by_name.get(entry.name, 0)
            if remaining <= 0:
                index += 1
                continue
            consumed_entry = inventory.pop(index)
            remaining_by_name[entry.name] = remaining - 1
            if on_fish_delivered:
                on_fish_delivered(consumed_entry)
        _mark_inventory_fish_counts_dirty()

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
                value = _calc_value(entry)
                mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
                unsellable_label = " [Unsellable]" if entry.is_unsellable else ""
                print(
                    f"{index}. {entry.name} "
                    f"({entry.kg:0.2f}kg){mutation_label}{unsellable_label} "
                    f"- {format_currency(value)}"
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
            if entry.is_unsellable:
                print("Este peixe está marcado como não vendável.")
                input("\nEnter para voltar.")
                return balance_local

            entry = inventory.pop(selected_index - 1)
            _mark_inventory_fish_counts_dirty()
            value = _calc_value(entry)
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
            sellable_entries = [entry for entry in inventory if not entry.is_unsellable]
            unsellable_entries = [entry for entry in inventory if entry.is_unsellable]
            if not sellable_entries:
                print("Nenhum peixe vendavel no inventario.")
                input("\nEnter para voltar.")
                return balance_local

            total = sum(_calc_value(entry) for entry in sellable_entries)
            if on_fish_sold or on_fish_delivered:
                for entry in sellable_entries:
                    if on_fish_sold:
                        on_fish_sold(entry)
                    if on_fish_delivered:
                        on_fish_delivered(entry)
            inventory[:] = unsellable_entries
            _mark_inventory_fish_counts_dirty()
            balance_local += total
            if on_money_earned:
                on_money_earned(total)
            print(
                f"Inventario vendido por {format_currency(total)}. "
                f"Itens nao vendaveis mantidos: {len(unsellable_entries)}."
            )
            input("\nEnter para voltar.")
            return balance_local

        print("Opcao invalida.")
        input("\nEnter para voltar.")
        return balance_local

    def _handle_buy_rod_action(current_balance: float) -> float:
        def _rod_summary_lines(rod: Optional[Rod], *, title: str) -> List[str]:
            luck_symbol = get_ui_symbol("LUCK")
            if rod is None:
                return [
                    title,
                    "Nome: Nenhuma",
                    f"{luck_symbol}: Nenhuma",
                    "KG Max: Nenhuma",
                    "Controle: Nenhuma",
                ]
            effective_rod = get_effective_rod(rod, resolved_rod_upgrade_state)
            summary_lines = [
                title,
                f"Nome: {rod.name}",
                (
                    f"{luck_symbol}: {format_upgrade_stat_value('luck', rod.luck)}"
                    if effective_rod.luck == rod.luck
                    else (
                        f"{luck_symbol}: {format_upgrade_stat_value('luck', rod.luck)} -> "
                        f"{format_upgrade_stat_value('luck', effective_rod.luck)}"
                    )
                ),
                (
                    f"KG Max: {format_upgrade_stat_value('kg_max', rod.kg_max)}"
                    if effective_rod.kg_max == rod.kg_max
                    else (
                        f"KG Max: {format_upgrade_stat_value('kg_max', rod.kg_max)} -> "
                        f"{format_upgrade_stat_value('kg_max', effective_rod.kg_max)}"
                    )
                ),
                (
                    f"Controle: {format_upgrade_stat_value('control', rod.control)}"
                    if effective_rod.control == rod.control
                    else (
                        f"Controle: {format_upgrade_stat_value('control', rod.control)} -> "
                        f"{format_upgrade_stat_value('control', effective_rod.control)}"
                    )
                ),
            ]
            upgrade_summary = format_upgrade_summary(rod, resolved_rod_upgrade_state)
            if upgrade_summary != "Sem melhorias":
                summary_lines.append(f"Melhorias: {upgrade_summary}")
            return summary_lines

        def _clip_cell(text: str, cell_width: int) -> str:
            if len(text) <= cell_width:
                return text
            if cell_width <= 3:
                return text[:cell_width]
            return text[: cell_width - 3] + "..."

        def _merge_columns(
            left_lines: Sequence[str],
            right_lines: Sequence[str],
            *,
            cell_width: int = 40,
        ) -> List[str]:
            merged: List[str] = []
            max_rows = max(len(left_lines), len(right_lines))
            for row in range(max_rows):
                left_text = _clip_cell(left_lines[row], cell_width) if row < len(left_lines) else ""
                right_text = _clip_cell(right_lines[row], cell_width) if row < len(right_lines) else ""
                merged.append(f"{left_text:<{cell_width}} | {right_text}")
            return merged

        def _show_rod_inspection_panel(selected_rod: Rod) -> bool:
            clear_screen()
            equipped_lines = _rod_summary_lines(equipped_rod, title="EQUIPPED_ROD")
            selected_lines = _rod_summary_lines(selected_rod, title="SELECTED_ROD")
            comparison_lines = _merge_columns(equipped_lines, selected_lines)
            flavor_text = selected_rod.description.strip() or "-"

            print_menu_panel(
                "Inspecao de Vara",
                breadcrumb="MERCADO > VARAS",
                header_lines=[
                    "Compare antes de confirmar:",
                    "",
                    *comparison_lines,
                    "",
                    f"[dim]{flavor_text}[/dim]",
                    "",
                    f"[bold yellow]Preco: {format_currency(selected_rod.price)}[/bold yellow]",
                ],
                options=[
                    MenuOption("S", "Confirmar compra"),
                    MenuOption("N", "Cancelar"),
                ],
                prompt="Confirmar compra? (S/N):",
                show_badge=False,
                width=92,
            )
            return input("> ").strip().lower() == "s"

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

        rod_options = [
            MenuOption(
                str(index),
                f"{rod.name} - {format_currency(rod.price)}",
                hint=format_rod_stats(rod),
            )
            for index, rod in enumerate(rods_for_sale, start=1)
        ]
        rod_options.append(MenuOption("0", "Voltar"))

        print_menu_panel(
            "Varas da Loja",
            breadcrumb="MERCADO > VARAS",
            header_lines=[
                f"Saldo atual: {format_currency(balance_local)}",
                "Selecione uma vara para inspecionar detalhes.",
            ],
            options=rod_options,
            prompt="Digite o numero da vara:",
            show_badge=False,
            width=92,
        )

        selection = input("> ").strip()
        if selection == "0":
            return balance_local
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

        if not _show_rod_inspection_panel(rod):
            print("Compra cancelada.")
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
            if entry.name == order.fish_name and not entry.is_unsellable
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
            if (
                entry.name == order.fish_name
                and not entry.is_unsellable
                and delivered < order.required_count
            ):
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

        selected_index: Optional[int] = None
        last_result: Optional[Dict[str, object]] = None
        session_notes: List[str] = []
        status_message = ""

        def _format_change_text(delta_value: float, text: str) -> str:
            if delta_value > 0:
                return f"{Style.DIM}{Fore.GREEN}{text}{Style.RESET_ALL}"
            if delta_value < 0:
                return f"{Style.DIM}{Fore.RED}{text}{Style.RESET_ALL}"
            return text

        def _read_appraise_action() -> str:
            if sys.stdin is not None and sys.stdin.isatty():
                return read_menu_choice(
                    "Escolha uma opcao: ",
                    instant_keys={"t"},
                ).strip().lower()
            return input("Escolha uma opcao: ").strip().lower()

        while True:
            if selected_index is None:
                clear_screen()
                header_lines = [
                    "=== Appraise ===",
                    "Selecione um peixe uma vez e rerole rapidamente.",
                    "0. Voltar",
                ]
                if status_message:
                    header_lines.append(f"Aviso: {status_message}")
                    status_message = ""
                print_spaced_lines(header_lines)
                for index, entry in enumerate(inventory, start=1):
                    value = _calc_value(entry)
                    cost = _appraise_cost(entry)
                    mutation_label = entry.mutation_name if entry.mutation_name else "Sem mutacao"
                    print(
                        f"{index}. {entry.name} [{entry.rarity}] "
                        f"({entry.kg:0.2f}kg | {mutation_label}) "
                        f"- Valor: {format_currency(value)} | Custo: {format_currency(cost)}"
                    )

                selection = input("Digite o numero do peixe: ").strip()
                if selection == "0":
                    return balance_local
                if not selection.isdigit():
                    status_message = "Entrada invalida."
                    continue

                selected_candidate = int(selection) - 1
                if not (0 <= selected_candidate < len(inventory)):
                    status_message = "Numero fora do intervalo."
                    continue

                selected_index = selected_candidate
                last_result = None
                session_notes = []
                status_message = ""
                continue

            if selected_index >= len(inventory):
                selected_index = None
                last_result = None
                session_notes = []
                status_message = "Peixe selecionado nao esta mais no inventario."
                continue

            entry = inventory[selected_index]
            profile = fish_by_name.get(entry.name)
            if not profile:
                selected_index = None
                last_result = None
                session_notes = []
                status_message = "Esse peixe nao pode ser avaliado agora."
                continue

            current_value = _calc_value(entry)
            cost = _appraise_cost(entry)
            mutation_label = entry.mutation_name if entry.mutation_name else "Sem mutacao"
            lines = [
                f"Peixe: {entry.name} [{entry.rarity}]",
                f"Atual: KG {entry.kg:0.2f} | Mutacao: {mutation_label}",
                f"Valor estimado: {format_currency(current_value)}",
                f"Custo do appraise: {format_currency(cost)}",
                f"Saldo: {format_currency(balance_local)}",
            ]
            if last_result:
                old_mutation = last_result["old_mutation"]
                new_mutation = last_result["new_mutation"]
                old_mutation_label = old_mutation if old_mutation else "Sem mutacao"
                new_mutation_label = new_mutation if new_mutation else "Sem mutacao"
                old_kg = float(last_result["old_kg"])
                new_kg = float(last_result["new_kg"])
                kg_delta = new_kg - old_kg
                old_value = float(last_result["old_value"])
                new_value = float(last_result["new_value"])
                value_delta = new_value - old_value
                kg_delta_label = _format_change_text(kg_delta, f"{kg_delta:+0.2f}kg")
                value_delta_label = _format_change_text(value_delta, f"{value_delta:+.2f}")
                lines.extend(
                    [
                        "",
                        "Comparacao do ultimo appraise:",
                        (
                            f"ANTES  - KG {old_kg:0.2f} | "
                            f"Mutacao: {old_mutation_label} | Valor: {format_currency(old_value)}"
                        ),
                        (
                            f"DEPOIS - KG {new_kg:0.2f} | "
                            f"Mutacao: {new_mutation_label} | Valor: {format_currency(new_value)}"
                        ),
                        f"Delta de KG: {kg_delta_label}",
                        f"Delta de valor: {value_delta_label}",
                    ]
                )
            if session_notes:
                lines.append("")
                lines.append("Notas:")
                lines.extend(f"- {note}" for note in session_notes if note)

            if status_message:
                lines.append(f"Aviso: {status_message}")
                status_message = ""

            clear_screen()
            print_menu_panel(
                "Appraise",
                header_lines=lines,
                options=[
                    MenuOption("T", "Appraise"),
                    MenuOption("1", "Trocar peixe"),
                    MenuOption("0", "Voltar"),
                ],
                prompt="Escolha uma opcao:",
                show_badge=False,
            )

            choice = _read_appraise_action()
            if choice == "0":
                return balance_local
            if choice == "1":
                selected_index = None
                last_result = None
                session_notes = []
                status_message = ""
                continue
            if choice != "t":
                status_message = "Opcao invalida."
                continue

            if balance_local < cost:
                status_message = "Saldo insuficiente para appraise."
                continue

            if entry.mutation_name:
                confirm = input(
                    f"{entry.name} possui mutacao {entry.mutation_name}. "
                    "Appraise pode trocar ou remover a mutacao. Confirmar? (s/n): "
                ).strip().lower()
                if confirm != "s":
                    status_message = "Appraise cancelado."
                    continue

            old_kg = entry.kg
            old_mutation = entry.mutation_name
            old_value = _calc_value(entry)

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
            if shiny_config is not None:
                entry.is_shiny = roll_shiny_on_appraise(shiny_config)
            new_value = _calc_value(entry)

            last_result = {
                "old_kg": old_kg,
                "new_kg": entry.kg,
                "old_mutation": old_mutation,
                "new_mutation": entry.mutation_name,
                "old_value": old_value,
                "new_value": new_value,
            }
            status_message = "Appraise concluido."
            session_notes = []

            if on_appraise_completed:
                notes = on_appraise_completed(entry)
                if notes:
                    session_notes.extend(note for note in notes if note)
            _refresh_crafting_unlocks()

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

    def _handle_upgrade_rod_action(
        current_balance: float,
        *,
        upgrade_gate_open: bool,
        upgrade_gate_reason: str,
    ) -> float:
        if not upgrade_gate_open:
            print(upgrade_gate_reason)
            input("\nEnter para voltar.")
            return current_balance

        balance_local = current_balance
        if not owned_rods:
            print("Nenhuma vara disponivel para melhoria.")
            input("\nEnter para voltar.")
            return balance_local

        clear_screen()
        rod_options = [
            MenuOption(
                str(index),
                rod.name,
                hint=format_upgrade_summary(rod, resolved_rod_upgrade_state),
            )
            for index, rod in enumerate(owned_rods, start=1)
        ]
        rod_options.append(MenuOption("0", "Voltar"))
        print_menu_panel(
            "Melhorar Vara",
            breadcrumb="MERCADO > MELHORAR VARA",
            header_lines=[
                f"Saldo atual: {format_currency(balance_local)}",
                "Escolha a vara que recebera a melhoria.",
            ],
            options=rod_options,
            prompt="Digite o numero da vara:",
            show_badge=False,
            width=92,
        )
        rod_choice = input("> ").strip()
        if rod_choice == "0":
            return balance_local
        if not rod_choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            return balance_local

        rod_index = int(rod_choice)
        if not (1 <= rod_index <= len(owned_rods)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            return balance_local

        selected_rod = owned_rods[rod_index - 1]
        effective_rod = get_effective_rod(selected_rod, resolved_rod_upgrade_state)
        stat_keys = [
            stat
            for stat in UPGRADEABLE_STATS
            if float(getattr(selected_rod, stat, 0.0)) != 0.0
        ]
        if not stat_keys:
            print("Esta vara nao possui stats elegiveis para melhoria.")
            input("\nEnter para voltar.")
            return balance_local
        stat_options: List[MenuOption] = []
        for index, stat in enumerate(stat_keys, start=1):
            info = UPGRADEABLE_STATS[stat]
            base_value = float(getattr(selected_rod, stat, 0.0))
            current_value = float(getattr(effective_rod, stat, base_value))
            current_bonus = resolved_rod_upgrade_state.get_bonus(selected_rod.name, stat)
            bonus_hint = (
                f" | Bonus salvo +{int(current_bonus * 100)}%"
                if current_bonus > 0
                else ""
            )
            stat_options.append(
                MenuOption(
                    str(index),
                    str(info["label"]),
                    hint=(
                        f"Base {format_upgrade_stat_value(stat, base_value)} | "
                        f"Atual {format_upgrade_stat_value(stat, current_value)}"
                        f"{bonus_hint}"
                    ),
                )
            )
        stat_options.append(MenuOption("0", "Voltar"))

        clear_screen()
        print_menu_panel(
            "Escolha o Stat",
            breadcrumb="MERCADO > MELHORAR VARA",
            header_lines=[
                f"Vara: {selected_rod.name}",
                f"Melhorias atuais: {format_upgrade_summary(selected_rod, resolved_rod_upgrade_state)}",
            ],
            options=stat_options,
            prompt="Digite o numero do stat:",
            show_badge=False,
            width=92,
        )
        stat_choice = input("> ").strip()
        if stat_choice == "0":
            return balance_local
        if not stat_choice.isdigit():
            print("Entrada invalida.")
            input("\nEnter para voltar.")
            return balance_local

        stat_index = int(stat_choice)
        if not (1 <= stat_index <= len(stat_keys)):
            print("Numero fora do intervalo.")
            input("\nEnter para voltar.")
            return balance_local

        selected_stat = stat_keys[stat_index - 1]
        stat_label = str(UPGRADEABLE_STATS[selected_stat]["label"])
        recipe = resolved_rod_upgrade_state.get_recipe(selected_rod.name, selected_stat)
        if recipe is None:
            requirements = generate_fish_requirements(
                _get_upgrade_pool_fish(),
                selected_rod,
                selected_stat,
            )
            if requirements:
                recipe = resolved_rod_upgrade_state.set_recipe(
                    selected_rod.name,
                    requirements,
                    stat=selected_stat,
                )
        if recipe is None:
            print("Nao foi possivel gerar requisitos para a melhoria nas pools desbloqueadas.")
            input("\nEnter para voltar.")
            return balance_local
        requirements = list(recipe.fish_requirements)

        cost = compute_upgrade_cost(selected_rod)
        requirement_lines, has_all_fish = _build_upgrade_requirement_lines(requirements)
        can_afford = balance_local >= cost
        current_bonus = resolved_rod_upgrade_state.get_bonus(selected_rod.name, selected_stat)
        current_value = (
            apply_stat_bonus(selected_rod, selected_stat, current_bonus)
            if current_bonus > 0
            else float(getattr(selected_rod, selected_stat, 0.0))
        )

        header_lines = [
            f"Vara: {selected_rod.name}",
            f"Stat escolhido: {stat_label}",
            (
                f"Valor base: "
                f"{format_upgrade_stat_value(selected_stat, float(getattr(selected_rod, selected_stat, 0.0)))}"
            ),
            f"Valor atual: {format_upgrade_stat_value(selected_stat, current_value)}",
            f"Custo: {format_currency(cost)}",
            "",
            "Peixes necessarios:",
            *requirement_lines,
        ]
        if not can_afford:
            header_lines.append(
                f"[red]Dinheiro insuficiente. Necessario: {format_currency(cost)}[/red]"
            )
        if not has_all_fish:
            header_lines.append("[red]Voce nao possui todos os peixes necessarios.[/red]")

        clear_screen()
        if can_afford and has_all_fish:
            options = [
                MenuOption("1", "Confirmar melhoria"),
                MenuOption("0", "Cancelar"),
            ]
            prompt = "Digite 1 para confirmar:"
        else:
            options = [MenuOption("0", "Voltar")]
            prompt = "Digite 0 para voltar:"
        print_menu_panel(
            "Confirmar Melhoria",
            breadcrumb="MERCADO > MELHORAR VARA",
            header_lines=header_lines,
            options=options,
            prompt=prompt,
            show_badge=False,
            width=92,
        )
        confirmation = input("> ").strip()
        if confirmation != "1" or not can_afford or not has_all_fish:
            return balance_local

        balance_local -= cost
        if on_money_spent:
            on_money_spent(cost)
        _consume_upgrade_requirements(requirements)

        previous_bonus = resolved_rod_upgrade_state.get_bonus(selected_rod.name, selected_stat)
        previous_value = (
            apply_stat_bonus(selected_rod, selected_stat, previous_bonus)
            if previous_bonus > 0
            else float(getattr(selected_rod, selected_stat, 0.0))
        )
        bonus = calculate_upgrade_bonus(
            list(requirements),
            stat=selected_stat,
            fish_by_name=fish_by_name,
        )
        resolved_rod_upgrade_state.apply_upgrade(selected_rod.name, selected_stat, bonus)
        resolved_rod_upgrade_state.clear_recipe(selected_rod.name, selected_stat)
        upgraded_value = apply_stat_bonus(selected_rod, selected_stat, bonus)

        clear_screen()
        print_menu_panel(
            "Melhoria Aplicada",
            breadcrumb="MERCADO > MELHORAR VARA",
            header_lines=[
                f"[green]Melhoria aplicada! {stat_label} +{int(bonus * 100)}%[/green]",
                f"Vara: {selected_rod.name}",
                (
                    f"{stat_label}: "
                    f"{format_upgrade_stat_value(selected_stat, previous_value)} -> "
                    f"{format_upgrade_stat_value(selected_stat, upgraded_value)}"
                ),
            ],
            options=[MenuOption("0", "Voltar")],
            prompt="Digite 0 para voltar:",
            show_badge=False,
            width=92,
        )
        input("> ")
        return balance_local

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

        upgrade_gate_open, upgrade_gate_reason = _upgrade_gate_status()

        crafting_gate_open, crafting_gate_reason = _crafting_gate_status()
        crafting_available = bool(
            crafting_definitions and crafting_state and crafting_progress
        )

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
            ]
        )
        if upgrade_gate_open:
            lines.append("6. Melhorar vara")
        if crafting_available and crafting_gate_open:
            lines.append("7. Crafting de varas")
        elif not crafting_available:
            lines.append("7. Crafting de varas (indisponivel)")
        lines.append("0. Voltar")
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
            balance = _handle_upgrade_rod_action(
                balance,
                upgrade_gate_open=upgrade_gate_open,
                upgrade_gate_reason=upgrade_gate_reason,
            )
            continue

        if choice == "7":
            balance = _handle_crafting_action(
                balance,
                crafting_gate_open=crafting_gate_open,
                crafting_gate_reason=crafting_gate_reason,
            )
            continue

        print("Opcao invalida.")
        input("\nEnter para voltar.")
