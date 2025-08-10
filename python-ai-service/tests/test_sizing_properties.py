import pytest

from psychrometrics import infiltration_load_l_per_day, derate_factor


@pytest.mark.parametrize(
    "temp_c",
    [10, 15, 20, 25, 30],
)
def test_lower_temp_lowers_derate(temp_c):
    # Holding RH fixed, derate factor should generally drop as temperature drops
    higher = derate_factor(temp_c, 60)
    lower = derate_factor(max(temp_c - 5, 1), 60)
    assert lower <= higher + 1e-6


def test_infiltration_load_zero_on_invalids():
    assert infiltration_load_l_per_day(0, 0.5, 22, 80, 50) == 0
    assert infiltration_load_l_per_day(-10, 0.5, 22, 80, 50) == 0


