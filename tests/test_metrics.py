from src.service import _rate

def test_rate_basic():
    assert _rate(1, 4) == 25.0

def test_rate_rounds_to_2_decimals():
    assert _rate(1, 3) == 33.33

def test_rate_zero_denominator():
    assert _rate(5, 0) == 0.0