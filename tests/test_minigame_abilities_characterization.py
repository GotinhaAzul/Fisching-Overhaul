from __future__ import annotations

from utils.pesca import (
    FishingAttempt,
    FishingMiniGame,
    _build_fishing_minigame,
    _render_colored_segment,
)
from utils.rods import Rod


def _make_game(
    sequence: list[str],
    *,
    pierce_chance: float = 0.0,
    can_curse: bool = False,
    curse_chance: float = 0.0,
    curse_time_penalty: float = 0.0,
    can_slam: bool = False,
    slam_chance: float = 0.0,
    slam_time_bonus: float = 0.0,
    vfx_seq_color: str | None = None,
    vfx_seq_count: int = 1,
    vfx_ability_color: str | None = None,
    vfx_ability_count: int = 1,
) -> FishingMiniGame:
    attempt = FishingAttempt(
        sequence=list(sequence),
        time_limit_s=30.0,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )
    game = FishingMiniGame(
        attempt,
        can_slam=can_slam,
        slam_chance=slam_chance,
        slam_time_bonus=slam_time_bonus,
        can_curse=can_curse,
        curse_chance=curse_chance,
        curse_time_penalty=curse_time_penalty,
        can_pierce=pierce_chance > 0,
        pierce_chance=pierce_chance,
        vfx_seq_color=vfx_seq_color,
        vfx_seq_count=vfx_seq_count,
        vfx_ability_color=vfx_ability_color,
        vfx_ability_count=vfx_ability_count,
    )
    game.begin()
    return game


# --- Pierce ---

def test_pierce_on_last_key_wrong_press_returns_success_characterization() -> None:
    """Pierce saves a wrong press on the final key and immediately returns success."""
    game = _make_game(["a", "b"], pierce_chance=1.0)
    game.handle_key("a")           # correct first key
    result = game.handle_key("x")  # wrong last key; pierce must fire → success
    assert result is not None
    assert result.success is True


def test_pierce_on_last_key_advances_index_to_done_characterization() -> None:
    """After pierce fires on the last key the game is done (no further key needed)."""
    game = _make_game(["a"], pierce_chance=1.0)
    result = game.handle_key("x")  # wrong; pierce fires; sequence length is 1
    assert result is not None
    assert result.success is True


def test_pierce_mid_sequence_advances_index_characterization() -> None:
    """Pierce on a middle key advances the index so typed length stays in sync."""
    game = _make_game(["a", "b", "c"], pierce_chance=1.0)
    game.handle_key("a")           # correct
    game.handle_key("x")           # wrong on index 1; pierce fires
    # index should now be 2; next correct key is 'c'
    result = game.handle_key("c")
    assert result is not None
    assert result.success is True


def test_pierce_mid_sequence_index_matches_typed_length_characterization() -> None:
    """After pierce the game's index equals len(typed), keeping HUD remaining in sync."""
    game = _make_game(["a", "b", "c"], pierce_chance=1.0)
    game.handle_key("a")   # correct → index=1, typed=['a']
    game.handle_key("x")   # wrong → pierce fires → index=2, typed=['a','x']
    assert game.index == len(game.typed)


def test_pierce_increments_activation_counter_characterization() -> None:
    game = _make_game(["a", "b"], pierce_chance=1.0)
    game.handle_key("a")
    game.handle_key("x")  # wrong; pierce fires
    assert game.pierce_activations == 1


def test_no_pierce_on_wrong_key_without_ability_characterization() -> None:
    game = _make_game(["a", "b"], pierce_chance=0.0)
    game.handle_key("a")
    result = game.handle_key("x")
    assert result is not None
    assert result.success is False


# --- Curse ---

def test_curse_activates_with_guaranteed_chance_characterization(monkeypatch) -> None:
    monkeypatch.setattr("utils.pesca.random.random", lambda: 0.0)

    game = _make_game(
        ["a", "b"],
        can_curse=True,
        curse_chance=1.0,
        curse_time_penalty=0.6,
    )

    game.handle_key("a")

    assert game.curse_activations == 1
    assert game.curse_penalty_accum_s == 0.6
    assert game.bonus_time_s == -0.6
    assert game.get_ability_counter_text() == "Curse! -0.6s"


def test_curse_and_slam_stack_as_net_time_delta_characterization(monkeypatch) -> None:
    rolls = iter([0.0, 0.0])
    monkeypatch.setattr("utils.pesca.random.random", lambda: next(rolls))

    game = _make_game(
        ["a", "b"],
        can_slam=True,
        slam_chance=1.0,
        slam_time_bonus=0.5,
        can_curse=True,
        curse_chance=1.0,
        curse_time_penalty=0.2,
    )

    game.handle_key("a")

    assert game.slam_activations == 1
    assert game.curse_activations == 1
    assert game.bonus_time_s == 0.3
    assert game.get_ability_counter_text() == "Curse! -0.2s"


def test_curse_causes_immediate_timeout_when_penalty_exhausts_time_characterization(
    monkeypatch,
) -> None:
    perf_values = iter([0.0, 0.05, 0.25])
    monkeypatch.setattr("utils.pesca.time.perf_counter", lambda: next(perf_values))
    monkeypatch.setattr("utils.pesca.random.random", lambda: 0.0)

    attempt = FishingAttempt(
        sequence=["a"],
        time_limit_s=0.2,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )
    game = FishingMiniGame(
        attempt,
        can_curse=True,
        curse_chance=1.0,
        curse_time_penalty=0.1,
    )
    game.begin()

    result = game.handle_key("a")

    assert result is not None
    assert result.success is False
    assert result.reason == "Tempo esgotado"
    assert game.curse_activations == 1
    assert game.typed == []


def test_curse_does_not_activate_with_zero_chance_characterization(monkeypatch) -> None:
    monkeypatch.setattr("utils.pesca.random.random", lambda: 0.0)

    game = _make_game(
        ["a", "b"],
        can_curse=True,
        curse_chance=0.0,
        curse_time_penalty=0.5,
    )

    game.handle_key("a")

    assert game.curse_activations == 0
    assert game.curse_penalty_accum_s == 0.0
    assert game.bonus_time_s == 0.0


def test_curse_does_not_activate_without_explicit_flag_characterization(monkeypatch) -> None:
    monkeypatch.setattr("utils.pesca.random.random", lambda: 0.0)

    game = _make_game(
        ["a", "b"],
        can_curse=False,
        curse_chance=1.0,
        curse_time_penalty=0.5,
    )

    game.handle_key("a")

    assert game.curse_activations == 0
    assert game.curse_penalty_accum_s == 0.0
    assert game.bonus_time_s == 0.0


def test_sequence_vfx_triggers_after_configured_valid_keys_characterization(
    monkeypatch,
) -> None:
    monkeypatch.setattr("utils.pesca.time.perf_counter", lambda: 0.0)

    game = _make_game(
        ["a", "b", "c"],
        vfx_seq_color="bright_cyan",
        vfx_seq_count=2,
    )

    game.handle_key("a")
    assert game.get_active_vfx_color() == ""
    game.handle_key("x")

    assert game.vfx_seq_progress == 0
    assert game.get_active_vfx_color() == "bright_cyan"


def test_ability_vfx_triggers_after_configured_activations_characterization(
    monkeypatch,
) -> None:
    monkeypatch.setattr("utils.pesca.time.perf_counter", lambda: 0.0)
    monkeypatch.setattr("utils.pesca.random.random", lambda: 0.0)

    game = _make_game(
        ["a", "b"],
        can_slam=True,
        slam_chance=1.0,
        slam_time_bonus=0.5,
        vfx_ability_color="red",
        vfx_ability_count=1,
    )

    game.handle_key("a")

    assert game.vfx_ability_progress == 0
    assert game.get_active_vfx_color() == "red"


def test_vfx_color_expires_after_short_window_characterization(monkeypatch) -> None:
    now = {"value": 0.0}
    monkeypatch.setattr("utils.pesca.time.perf_counter", lambda: now["value"])

    game = _make_game(
        ["a"],
        vfx_seq_color="green",
        vfx_seq_count=1,
    )

    game.handle_key("a")
    assert game.get_active_vfx_color() == "green"

    now["value"] = 1.0
    assert game.get_active_vfx_color() == ""


def test_render_colored_segment_falls_back_to_plain_text_when_color_is_invalid_characterization() -> None:
    rendered = _render_colored_segment("Seq: ", "A B", color="not a real color")

    assert rendered == "Seq: A B"


def test_minigame_normalizes_vfx_values_characterization() -> None:
    attempt = FishingAttempt(
        sequence=["a"],
        time_limit_s=30.0,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )

    game = FishingMiniGame(
        attempt,
        vfx_seq_color="  bright_cyan  ",
        vfx_seq_count=0,
        vfx_ability_color="   ",
        vfx_ability_count="abc",
    )

    assert game.vfx_seq_color == "bright_cyan"
    assert game.vfx_seq_count == 1
    assert game.vfx_ability_color is None
    assert game.vfx_ability_count == 1


def test_build_fishing_minigame_keeps_vfx_config_for_frenzy_characterization() -> None:
    rod = Rod(
        name="Rod VFX",
        luck=0.0,
        kg_max=10.0,
        control=0.0,
        description="",
        price=0.0,
        can_slam=True,
        slam_chance=1.0,
        slam_time_bonus=0.5,
        vfxseq="bright_cyan",
        vfxseqcount=2,
        vfxability="red",
        vfxabilitycount=3,
    )
    attempt = FishingAttempt(
        sequence=["a", "b"],
        time_limit_s=30.0,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )

    frenzy_game = _build_fishing_minigame(
        attempt,
        rod,
        include_rod_abilities=False,
    )

    assert frenzy_game.can_slam is False
    assert frenzy_game.vfx_seq_color == "bright_cyan"
    assert frenzy_game.vfx_seq_count == 2
    assert frenzy_game.vfx_ability_color == "red"
    assert frenzy_game.vfx_ability_count == 3


def test_build_fishing_minigame_includes_rod_abilities_by_default_characterization() -> None:
    rod = Rod(
        name="Rod Abilities",
        luck=0.0,
        kg_max=10.0,
        control=0.0,
        description="",
        price=0.0,
        can_slash=True,
        slash_chance=0.25,
        slash_power=2,
        can_slam=True,
        slam_chance=0.5,
        slam_time_bonus=0.75,
        can_curse=True,
        curse_chance=0.4,
        curse_time_penalty=0.35,
        can_pierce=True,
        pierce_chance=0.6,
        can_greed=True,
        greed_chance=0.2,
    )
    attempt = FishingAttempt(
        sequence=["a", "b"],
        time_limit_s=30.0,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )

    game = _build_fishing_minigame(attempt, rod)

    assert game.can_slash is True
    assert game.slash_chance == 0.25
    assert game.slash_power == 2
    assert game.can_slam is True
    assert game.slam_chance == 0.5
    assert game.slam_time_bonus == 0.75
    assert game.can_curse is True
    assert game.curse_chance == 0.4
    assert game.curse_time_penalty == 0.35
    assert game.can_pierce is True
    assert game.pierce_chance == 0.6
    assert game.can_greed is True
    assert game.greed_chance == 0.2
