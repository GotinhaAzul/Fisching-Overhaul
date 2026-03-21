import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def _parse_number(
    raw_value: object,
    default: float = 0.0,
    *,
    percent_suffix_as_fraction: bool,
) -> float:
    if isinstance(raw_value, str):
        text_value = raw_value.strip()
        if not text_value:
            return default
        if text_value.endswith("%"):
            text_value = text_value[:-1].strip()
            try:
                parsed = float(text_value)
            except ValueError:
                return default
            if percent_suffix_as_fraction:
                return parsed / 100.0
            return parsed
        try:
            return float(text_value)
        except ValueError:
            return default
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _normalize_probability(raw_value: object) -> float:
    chance = _parse_number(raw_value, 0.0, percent_suffix_as_fraction=True)
    if chance > 1.0:
        chance /= 100.0
    return max(0.0, min(1.0, chance))


def _safe_float(raw_value: object, default: float = 0.0) -> float:
    return _parse_number(raw_value, default, percent_suffix_as_fraction=False)


def _safe_int(raw_value: object, default: int = 0) -> int:
    parsed = _parse_number(raw_value, float(default), percent_suffix_as_fraction=False)
    try:
        return int(parsed)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_bool(raw_value: object, default: bool = False) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if raw_value is None:
        return default
    return bool(raw_value)


@dataclass(frozen=True)
class Rod:
    name: str
    luck: float
    kg_max: float
    control: float
    description: str
    price: float
    can_slash: bool = False
    slash_chance: float = 0.0
    slash_power: int = 1
    can_slam: bool = False
    slam_chance: float = 0.0
    slam_time_bonus: float = 0.0
    can_recover: bool = False
    recover_chance: float = 0.0
    can_pierce: bool = False
    pierce_chance: float = 0.0
    can_dupe: bool = False
    dupe_chance: float = 0.0
    can_frenzy: bool = False
    frenzy_chance: float = 0.0
    can_greed: bool = False
    greed_chance: float = 0.0
    can_alter: bool = False
    timecount: float = 0.0
    hardcount: float = 0.0
    unlocked_default: bool = False
    unlocks_with_pool: str = ""
    counts_for_bestiary_completion: bool = True
    shiny_override: Optional[float] = None


def load_rods(base_dir: Path) -> List[Rod]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório de varas não encontrado: {base_dir}")

    rods: List[Rod] = []
    for rod_path in sorted(base_dir.glob("*.json")):
        try:
            with rod_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Aviso: vara ignorada ({rod_path}): {exc}")
            continue
        if not isinstance(data, dict):
            print(f"Aviso: vara ignorada ({rod_path}): formato invalido.")
            continue

        name = data.get("name")
        if not name:
            continue
        raw_unlocks_with_pool = data.get("unlockswithpool", data.get("unlocks_with_pool", ""))
        unlocks_with_pool = (
            raw_unlocks_with_pool.strip()
            if isinstance(raw_unlocks_with_pool, str)
            else ""
        )
        raw_counts_flag = data.get("counts_for_bestiary_completion")
        if isinstance(raw_counts_flag, bool):
            counts_for_bestiary_completion = raw_counts_flag
        else:
            counts_for_bestiary_completion = not _safe_bool(
                data.get("exclude_from_bestiary_completion", False)
            )
        raw_shiny_override = data.get("shiny_override")
        shiny_override = (
            _normalize_probability(raw_shiny_override)
            if raw_shiny_override is not None
            else None
        )

        rods.append(
            Rod(
                name=name,
                luck=_safe_float(data.get("luck", 0.0)),
                kg_max=_safe_float(data.get("kg_max", 0.0)),
                control=_safe_float(data.get("control", 0.0)),
                description=str(data.get("description", "")),
                price=_safe_float(data.get("price", 0.0)),
                can_slash=_safe_bool(data.get("can_slash", False)),
                slash_chance=_normalize_probability(data.get("slash_chance", 0.0)),
                slash_power=max(1, _safe_int(data.get("slash_power", 1), 1)),
                can_slam=_safe_bool(data.get("can_slam", False)),
                slam_chance=_normalize_probability(data.get("slam_chance", 0.0)),
                slam_time_bonus=max(0.0, _safe_float(data.get("slam_time_bonus", 0.0))),
                can_recover=_safe_bool(data.get("can_recover", False)),
                recover_chance=_normalize_probability(data.get("recover_chance", 0.0)),
                can_pierce=_safe_bool(data.get("can_pierce", False)),
                pierce_chance=_normalize_probability(data.get("pierce_chance", 0.0)),
                can_dupe=_safe_bool(data.get("can_dupe", False)),
                dupe_chance=_normalize_probability(data.get("dupe_chance", 0.0)),
                can_frenzy=_safe_bool(data.get("can_frenzy", False)),
                frenzy_chance=_normalize_probability(data.get("frenzy_chance", 0.0)),
                can_greed=_safe_bool(data.get("can_greed", False)),
                greed_chance=_normalize_probability(data.get("greed_chance", 0.0)),
                can_alter=_safe_bool(data.get("can_alter", False)),
                timecount=_safe_float(data.get("timecount", data.get("time_count", 0.0))),
                hardcount=_safe_float(data.get("hardcount", data.get("hard_count", 0.0))),
                unlocked_default=_safe_bool(data.get("unlocked_default", False)),
                unlocks_with_pool=unlocks_with_pool,
                counts_for_bestiary_completion=counts_for_bestiary_completion,
                shiny_override=shiny_override,
            )
        )

    if not rods:
        raise RuntimeError("Nenhuma vara encontrada. Verifique os arquivos em /rods.")

    return rods
