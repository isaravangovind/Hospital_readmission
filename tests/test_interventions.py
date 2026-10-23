import pytest
from pydantic import ValidationError
from src.models import InterventionStatus as S, InterventionUpdate
from src.service import check_transition, InvalidStatusTransition

def test_forward_allowed():
    check_transition(S.PENDING_REVIEW, S.ASSIGNED)          # no error = pass

def test_skip_ahead_allowed():
    check_transition(S.ASSIGNED, S.CLOSED)

def test_same_status_allowed():
    check_transition(S.CONTACTED, S.CONTACTED)

def test_backward_rejected():
    with pytest.raises(InvalidStatusTransition):
        check_transition(S.CONTACTED, S.ASSIGNED)

def test_closed_is_terminal():
    with pytest.raises(InvalidStatusTransition):
        check_transition(S.CLOSED, S.PENDING_REVIEW)

def test_empty_body_rejected():
    with pytest.raises(ValidationError):
        InterventionUpdate()

def test_assigned_to_is_stripped():
    assert InterventionUpdate(assigned_to="  Nurse Priya ").assigned_to == "Nurse Priya"

# TODO: test that assigned_to="   " is rejected
# TODO: test that status="DONE" is rejected
# TODO: test that status=None (sent explicitly) is rejected

