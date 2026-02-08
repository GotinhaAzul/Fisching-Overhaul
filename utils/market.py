from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

from utils.dialogue import get_market_line
from utils.inventory import InventoryEntry, calculate_entry_value
from utils.levels import apply_xp_gain
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


def show_market(
    inventory: List[InventoryEntry],
    balance: float,
    selected_pool: "FishingPool",
    level: int,
    xp: int,
    available_rods: List[Rod],
    owned_rods: List[Rod],
    *,
    pool_orders: Optional[Dict[str, PoolMarketOrder]] = None,
    unlocked_rods: Optional[set[str]] = None,
    on_money_earned=None,
    on_money_spent=None,
    on_fish_delivered=None,
) -> tuple[float, int, int]:
    pool_orders = pool_orders if pool_orders is not None else {}
    while True:
        clear_screen()
        order = get_pool_market_order(selected_pool, pool_orders)
        order_line = "4. Pedido rotativo da pool"
        if order:
            time_left_s = max(0, int(order.expires_at - time.time()))
            minutes_left = time_left_s // 60
            seconds_left = time_left_s % 60
            order_line = (
                "4. Pedido rotativo da pool "
                f"({order.required_count}x {order.fish_name} [{order.rarity}] | "
                f"{minutes_left:02d}:{seconds_left:02d})"
            )
        print_spaced_lines([
            "🛒 === Mercado ===",
            get_market_line(),
            f"Pool atual: {selected_pool.name}",
            f"Dinheiro: {format_currency(balance)}",
            "1. Vender peixe individual",
            "2. Vender inventário inteiro",
            "3. Comprar vara",
            order_line,
            "0. Voltar",
        ])

        choice = input("Escolha uma opção: ").strip()
        if choice == "0":
            return balance, level, xp

        if choice == "1":
            clear_screen()
            if not inventory:
                print("Inventário vazio.")
                input("\nEnter para voltar.")
                continue

            print_spaced_lines(["Escolha o peixe para vender:"])
            for idx, entry in enumerate(inventory, start=1):
                value = calculate_entry_value(entry)
                mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
                print(
                    f"{idx}. {entry.name} "
                    f"({entry.kg:0.2f}kg){mutation_label} - {format_currency(value)}"
                )

            selection = input("Digite o número do peixe: ").strip()
            if not selection.isdigit():
                print("Entrada inválida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(inventory)):
                print("Número fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            entry = inventory.pop(idx - 1)
            value = calculate_entry_value(entry)
            balance += value
            if on_money_earned:
                on_money_earned(value)
            if on_fish_delivered:
                on_fish_delivered(entry)
            mutation_label = f" ✨ {entry.mutation_name}" if entry.mutation_name else ""
            print(
                f"Vendeu {entry.name} ({entry.kg:0.2f}kg){mutation_label} "
                f"por {format_currency(value)}."
            )
            input("\nEnter para voltar.")
            continue

        if choice == "4":
            clear_screen()
            order = get_pool_market_order(selected_pool, pool_orders)
            if not order:
                print("Não há pedido disponível para esta pool agora.")
                input("\nEnter para voltar.")
                continue

            matching_entries = [
                entry
                for entry in inventory
                if entry.name == order.fish_name
            ]
            print_spaced_lines([
                "📦 Pedido rotativo",
                f"Pool: {order.pool_name}",
                f"Solicitação: {order.required_count}x {order.fish_name} [{order.rarity}]",
                f"Disponível no inventário: {len(matching_entries)}",
                f"Recompensa: {format_currency(order.reward_money)} + {order.reward_xp} XP",
            ])

            if len(matching_entries) < order.required_count:
                print("Você ainda não tem peixes suficientes para cumprir o pedido.")
                input("\nEnter para voltar.")
                continue

            confirm = input("Entregar agora? (s/n): ").strip().lower()
            if confirm != "s":
                continue

            delivered = 0
            remaining_inventory: List[InventoryEntry] = []
            for entry in inventory:
                if entry.name == order.fish_name and delivered < order.required_count:
                    delivered += 1
                    if on_fish_delivered:
                        on_fish_delivered(entry)
                    continue
                remaining_inventory.append(entry)

            inventory[:] = remaining_inventory
            balance += order.reward_money
            level, xp, level_ups = apply_xp_gain(level, xp, order.reward_xp)
            if on_money_earned:
                on_money_earned(order.reward_money)
            print(
                f"Pedido entregue! Você recebeu {format_currency(order.reward_money)} "
                f"e {order.reward_xp} XP."
            )
            if level_ups:
                print(f"⬆️ Você subiu {level_ups} nível(is)!")
            pool_orders.pop(selected_pool.name, None)
            input("\nEnter para voltar.")
            continue

        if choice == "2":
            clear_screen()
            if not inventory:
                print("Inventário vazio.")
                input("\nEnter para voltar.")
                continue

            total = sum(calculate_entry_value(entry) for entry in inventory)
            if on_fish_delivered:
                for entry in inventory:
                    on_fish_delivered(entry)
            inventory.clear()
            balance += total
            if on_money_earned:
                on_money_earned(total)
            print(f"Inventário vendido por {format_currency(total)}.")
            input("\nEnter para voltar.")
            continue

        if choice == "3":
            clear_screen()
            rods_for_sale = [
                rod
                for rod in available_rods
                if rod.name not in {r.name for r in owned_rods}
                and (unlocked_rods is None or rod.name in unlocked_rods)
            ]
            if not rods_for_sale:
                print("Nenhuma vara disponível para compra.")
                input("\nEnter para voltar.")
                continue

            print_spaced_lines(["Varas disponíveis:"])
            for idx, rod in enumerate(rods_for_sale, start=1):
                print(format_rod_entry(idx, rod))
                print(f"   {rod.description}")

            selection = input("Digite o número da vara: ").strip()
            if not selection.isdigit():
                print("Entrada inválida.")
                input("\nEnter para voltar.")
                continue

            idx = int(selection)
            if not (1 <= idx <= len(rods_for_sale)):
                print("Número fora do intervalo.")
                input("\nEnter para voltar.")
                continue

            rod = rods_for_sale[idx - 1]
            if balance < rod.price:
                print("Saldo insuficiente.")
                input("\nEnter para voltar.")
                continue

            balance -= rod.price
            if on_money_spent:
                on_money_spent(rod.price)
            owned_rods.append(rod)
            print(f"Comprou {rod.name} por {format_currency(rod.price)}.")
            input("\nEnter para voltar.")
            continue

        print("Opção inválida.")
        input("\nEnter para voltar.")
