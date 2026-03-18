from __future__ import annotations

import pytest

from utils.pesca import _calculate_frenzy_time_limit


def test_frenzy_time_limit_keeps_existing_scaling_for_long_sequences_characterization() -> None:
    assert _calculate_frenzy_time_limit(4.0, sequence_len=4, time_factor=0.6885) == pytest.approx(
        2.754
    )


def test_frenzy_time_limit_caps_two_key_rounds_characterization() -> None:
    assert _calculate_frenzy_time_limit(4.0, sequence_len=2, time_factor=0.6885) == pytest.approx(
        1.8
    )


def test_frenzy_time_limit_caps_one_key_rounds_characterization() -> None:
    assert _calculate_frenzy_time_limit(4.0, sequence_len=1, time_factor=0.61965) == pytest.approx(
        1.2
    )


def test_frenzy_time_limit_uses_point_three_second_floor_characterization() -> None:
    assert _calculate_frenzy_time_limit(0.4, sequence_len=1, time_factor=0.30) == pytest.approx(
        0.3
    )
