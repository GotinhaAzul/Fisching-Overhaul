from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PerfectCatchConfig:
    enabled: bool = True
    threshold_ratio: float = 0.20
    xp_multiplier: float = 1.50


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float) -> float:
    try:
        if isinstance(value, bool):
            raise TypeError("bool is not a valid float input here")
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "sim"}:
            return True
        if normalized in {"0", "false", "no", "off", "nao", "não"}:
            return False
    return default


def _coerce_bool_field(
    payload: dict[str, Any],
    *,
    key: str,
    default: bool,
    source_label: str,
) -> bool:
    if key not in payload:
        return default

    raw_value = payload.get(key)
    parsed = safe_bool(raw_value, default)
    if parsed == default and not isinstance(raw_value, (bool, int, float, str)):
        print(
            f"Aviso: perfect_catch.{key} invalido em {source_label}; "
            f"usando {default}."
        )
    elif isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized not in {"1", "true", "yes", "on", "sim", "0", "false", "no", "off", "nao", "não"}:
            print(
                f"Aviso: perfect_catch.{key} invalido em {source_label}; "
                f"usando {default}."
            )
    return parsed


def _coerce_float_field(
    payload: dict[str, Any],
    *,
    key: str,
    default: float,
    source_label: str,
    minimum: float,
    maximum: float,
) -> float:
    if key not in payload:
        return default

    raw_value = payload.get(key)
    parsed = safe_float(raw_value, default)
    if parsed == default:
        try:
            if isinstance(raw_value, bool):
                raise TypeError("bool")
            float(raw_value)
        except (TypeError, ValueError):
            print(
                f"Aviso: perfect_catch.{key} invalido em {source_label}; "
                f"usando {default:0.2f}."
            )
            return default

    clamped = clamp(parsed, minimum, maximum)
    if clamped != parsed:
        print(
            f"Aviso: perfect_catch.{key} fora do intervalo em {source_label}; "
            f"ajustado para {clamped:0.2f}."
        )
    return clamped


def parse_perfect_catch_config(
    raw_config: Any,
    *,
    source_label: str,
    fallback: Optional[PerfectCatchConfig] = None,
    allow_missing: bool = False,
) -> Optional[PerfectCatchConfig]:
    fallback_cfg = fallback or PerfectCatchConfig()
    if raw_config is None:
        if allow_missing:
            return None
        return fallback_cfg

    if not isinstance(raw_config, dict):
        print(
            f"Aviso: perfect_catch invalido em {source_label}; "
            "esperado objeto JSON, usando fallback."
        )
        return fallback_cfg

    enabled = _coerce_bool_field(
        raw_config,
        key="enabled",
        default=fallback_cfg.enabled,
        source_label=source_label,
    )
    threshold_ratio = _coerce_float_field(
        raw_config,
        key="threshold_ratio",
        default=fallback_cfg.threshold_ratio,
        source_label=source_label,
        minimum=0.10,
        maximum=1.00,
    )
    xp_multiplier = _coerce_float_field(
        raw_config,
        key="xp_multiplier",
        default=fallback_cfg.xp_multiplier,
        source_label=source_label,
        minimum=1.00,
        maximum=5.00,
    )
    return PerfectCatchConfig(
        enabled=enabled,
        threshold_ratio=threshold_ratio,
        xp_multiplier=xp_multiplier,
    )


def is_perfect_catch(elapsed_s: float, total_s: float, cfg: PerfectCatchConfig) -> bool:
    if not cfg.enabled:
        return False
    if total_s <= 0:
        return False
    elapsed_ratio = max(0.0, elapsed_s) / max(0.001, total_s)
    return elapsed_ratio <= cfg.threshold_ratio


def resolve_hud_color(elapsed_ratio: float, threshold_ratio: float) -> str:
    safe_elapsed = clamp(elapsed_ratio, 0.0, 1.0)
    safe_threshold = clamp(threshold_ratio, 0.10, 1.00)
    if safe_elapsed <= 0.35:
        return "bright_cyan"
    if safe_elapsed <= safe_threshold:
        return "green"
    if safe_elapsed <= 0.90:
        return "yellow"
    return "red"
