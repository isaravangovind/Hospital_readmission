from src.service import calculate_risk_score, map_risk_level, explain_risk
from src.models import RiskLevel

ZERO = dict(number_inpatient=0, number_emergency=0, number_outpatient=0,
            time_in_hospital=0, num_medications=0)

def score(**changes):
    return calculate_risk_score(**{**ZERO, **changes})

def test_all_zero_is_zero():
    assert score() == 0

def test_inpatient_threshold():
    assert score(number_inpatient=2) == 0
    assert score(number_inpatient=3) == 3

def test_emergency_threshold():
    assert score(number_emergency=1) == 0
    assert score(number_emergency=2) == 2

# TODO: write the same for outpatient (2/3), time_in_hospital (6/7), num_medications (19/20)
def test_outpatient_threshold():
    assert score(number_outpatient=2) == 0
    assert score(number_outpatient=3) == 1
def test_time_in_hospital_threshold():
    assert score(time_in_hospital=6) == 0
    assert score(time_in_hospital=7) == 1
def test_num_medications_threshold():
    assert score(num_medications=19) == 0
    assert score(num_medications=20) == 1


def test_max_score_is_8():
    assert score(number_inpatient=9, number_emergency=9, number_outpatient=9,
                 time_in_hospital=14, num_medications=50) == 8

def test_level_boundaries():
    assert map_risk_level(2) == RiskLevel.LOW
    assert map_risk_level(3) == RiskLevel.MEDIUM
    assert map_risk_level(4) == RiskLevel.MEDIUM
    assert map_risk_level(5) == RiskLevel.HIGH

def test_explain_lists_fired_rules():
    row = {**ZERO, "number_inpatient": 3, "num_medications": 25}
    assert explain_risk(row) == ["3+ prior inpatient visits", "20+ medications"]