from __future__ import annotations

from utils.pesca import FishingAttempt, FishingMiniGame


def _make_game(sequence: list[str], *, pierce_chance: float = 0.0) -> FishingMiniGame:
    attempt = FishingAttempt(
        sequence=list(sequence),
        time_limit_s=30.0,
        allowed_keys=list("abcdefghijklmnopqrstuvwxyz"),
    )
    game = FishingMiniGame(
        attempt,
        can_pierce=pierce_chance > 0,
        pierce_chance=pierce_chance,
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
