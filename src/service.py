from src.models import (RiskLevel, EncounterOut, EncounterList,
                        CareQueueItem, CareQueueList)
from src import repository
from src.models import InterventionStatus, STATUS_ORDER, InterventionUpdate, InterventionOut, OperationsSummary, ReadmissionAnalysis, RiskGroupOutcome, ManagementDashboard, STATUS_ORDER




class DomainError(Exception):
    """Base for business-rule errors. main.py maps these to HTTP codes."""

class EncounterNotFound(DomainError):        # → 404
    pass

class NotInCareQueue(DomainError):           # → 409
    pass

class InvalidStatusTransition(DomainError):  # → 409
    pass

from src.models import RiskLevel
from src.repository import *
from src.database import get_connection

# (field, threshold, points, reason)
RISK_RULES = [
    ("number_inpatient",  3,  3, "3+ prior inpatient visits"),
    ("number_emergency",  2,  2, "2+ prior emergency visits"),
    ("number_outpatient", 3,  1, "3+ prior outpatient visits"),
    ("time_in_hospital",  7,  1, "Hospital stay of 7+ days"),
    ("num_medications",   20, 1, "20+ medications"),
]

def calculate_risk_score(number_inpatient, number_emergency, number_outpatient,
                         time_in_hospital, num_medications) -> int:
    values = {
        "number_inpatient": number_inpatient,
        "number_emergency": number_emergency,
        "number_outpatient": number_outpatient,
        "time_in_hospital": time_in_hospital,
        "num_medications": num_medications,
    }
    # TODO: loop over RISK_RULES; add `points` when values[field] >= threshold
    score = 0
    for field, threshold, points, reason in RISK_RULES:
        if values[field] >= threshold:
            score += points
    return score

def map_risk_level(score: int) -> RiskLevel:
    # 0–2 → LOW, 3–4 → MEDIUM, 5+ → HIGH
    # TODO: check from highest down: if score >= 5 ... elif score >= 3 ...
    if score >= 5:
        return RiskLevel.HIGH
    elif score >= 3:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW

def explain_risk(row: dict) -> list[str]:
    # TODO: return [reason for field, threshold, _, reason in RISK_RULES if row[field] >= threshold]
    return [reason for field, threshold, _, reason in RISK_RULES if row[field] >= threshold]

def score_all_encounters() -> int:
    with get_connection() as conn:
        inputs = fetch_scoring_inputs(conn)

        updates = []
        for row in inputs:
            score = calculate_risk_score(
                number_inpatient=row["number_inpatient"],
                number_emergency=row["number_emergency"],
                number_outpatient=row["number_outpatient"],
                time_in_hospital=row["time_in_hospital"],
                num_medications=row["num_medications"],
            )
            level = map_risk_level(score)
            # TODO: append the tuple in the order bulk_update_scores expects
            #       hint: use level.value so Postgres gets the plain string 'HIGH'
            updates.append((score, level.value, row["encounter_id"]))
        if not updates:
            return 0
        return bulk_update_scores(conn, updates)

def build_care_queue() -> int:
    # TODO: open a connection, call repository.populate_queue(conn), return the count
    with get_connection() as conn:
        return populate_queue(conn)


def list_encounters(limit: int, offset: int) -> EncounterList:
    with get_connection() as conn:
        total = repository.count_encounters(conn)
        rows = repository.list_encounters(conn, limit, offset)
    return EncounterList(
        items=[EncounterOut(**r) for r in rows],
        limit=limit, offset=offset, total=total,
    )

def get_encounter(encounter_id: int) -> EncounterOut:
    with get_connection() as conn:
        row = repository.get_encounter(conn, encounter_id)
    # TODO: if row is None → raise EncounterNotFound(f"Encounter {encounter_id} not found")
    # TODO: return EncounterOut(**row)
    if row is None:
        raise EncounterNotFound(f"Encounter {encounter_id} not found")
    return EncounterOut(**row)



def _queue(levels: list[RiskLevel], limit: int, offset: int) -> CareQueueList:
    level_values = [lvl.value for lvl in levels]
    with get_connection() as conn:
        total = repository.count_care_queue(conn, level_values)
        rows = repository.get_care_queue(conn, level_values, limit, offset)
    items = [CareQueueItem(**r, risk_reasons=explain_risk(r)) for r in rows]
    return CareQueueList(items=items, limit=limit, offset=offset, total=total)

def get_care_queue(limit: int, offset: int) -> CareQueueList:
    return _queue([RiskLevel.MEDIUM, RiskLevel.HIGH], limit, offset)

def get_high_risk_queue(limit: int, offset: int) -> CareQueueList:
    # TODO: one line, like above
    return _queue([RiskLevel.HIGH], limit, offset)


def check_transition(current: InterventionStatus, new: InterventionStatus) -> None:
    # TODO: if STATUS_ORDER.index(new) < STATUS_ORDER.index(current):
    #           raise InvalidStatusTransition(f"Cannot move from {current.value} to {new.value}")
    if STATUS_ORDER.index(new) < STATUS_ORDER.index(current):
        raise InvalidStatusTransition(f"Cannot move from {current.value} to {new.value}")
    return None

def update_intervention(encounter_id: int, update: InterventionUpdate) -> InterventionOut:
    fields = update.model_dump(exclude_unset=True, mode="json")

    with get_connection() as conn:
        # 1) encounter exists?
        if repository.get_encounter(conn, encounter_id) is None:
            raise EncounterNotFound(f"Encounter {encounter_id} not found")

        # 2) in the care queue?
        current = repository.get_intervention(conn, encounter_id)
        if current is None:
            raise NotInCareQueue(
                f"Encounter {encounter_id} is not in the care queue (LOW risk)"
            )

        # 3) forward-only rule
        if update.status is not None:
            check_transition(InterventionStatus(current["status"]), update.status)

        # 4) save only what was sent
        row = repository.update_intervention(conn, encounter_id, fields)

    return InterventionOut(**row)

def _rate(numerator: int, denominator: int) -> float:
    """Percent, 2 decimals; 0.0 when denominator is 0 (D6)."""
    return round(numerator / denominator * 100, 2) if denominator else 0.0

IN_PROGRESS = ("ASSIGNED", "CONTACTED", "FOLLOW_UP_SCHEDULED")

def get_operations_summary() -> OperationsSummary:
    with get_connection() as conn:
        by_level = repository.count_by_risk_level(conn)
        by_status = repository.count_interventions_by_status(conn)

    high = by_level.get("HIGH", 0)
    medium = by_level.get("MEDIUM", 0)
    low = by_level.get("LOW", 0)

    return OperationsSummary(
        total_encounters=sum(by_level.values()),
        high_risk=high,
        medium_risk=medium,
        low_risk=low,
        unscored=by_level.get(None, 0),
        queue_size=high + medium,
        pending_interventions=by_status.get("PENDING_REVIEW", 0),
        in_progress_interventions=sum(by_status.get(s, 0) for s in IN_PROGRESS),
        completed_interventions=by_status.get("CLOSED", 0),
    )

def get_readmission_analysis() -> ReadmissionAnalysis:
    with get_connection() as conn:
        rows = repository.readmission_by_risk_level(conn)

    by_level = {r["risk_level"]: r for r in rows}

    def enc(level):  return by_level.get(level, {}).get("encounters", 0)
    def r30(level):  return by_level.get(level, {}).get("readmitted_under_30", 0)

    total = sum(r["encounters"] for r in rows)
    total_r30 = sum(r["readmitted_under_30"] for r in rows)

    groups = [
        RiskGroupOutcome(
            risk_level=level,
            encounters=enc(level),
            readmitted_under_30_days=r30(level),
            readmission_rate=_rate(r30(level), enc(level)),
        )
        for level in ("LOW", "MEDIUM", "HIGH")
    ]

    baseline_rate = _rate(total_r30, total)
    high_rate = _rate(r30("HIGH"), enc("HIGH"))

    return ReadmissionAnalysis(
        baseline_encounters=total,
        baseline_readmitted_under_30_days=total_r30,
        baseline_readmission_rate=baseline_rate,
        groups=groups,
        high_risk_lift=round(high_rate / baseline_rate, 2) if baseline_rate else 0.0,
        # queue_share_of_encounters=  # TODO: _rate(MEDIUM + HIGH encounters, total)
        # queue_capture_of_readmissions=  # TODO: _rate(MEDIUM + HIGH <30, total_r30)
        # → 10.15, 15.23
        queue_share_of_encounters=_rate(enc("MEDIUM") + enc("HIGH"), total),
        queue_capture_of_readmissions=_rate(r30("HIGH") + r30("MEDIUM"), total_r30)
    )

def get_management_dashboard() -> ManagementDashboard:
    summary = get_operations_summary()
    analysis = get_readmission_analysis()
    with get_connection() as conn:
        by_status = repository.count_interventions_by_status(conn)

    high_group = next(g for g in analysis.groups if g.risk_level == "HIGH")

    return ManagementDashboard(
        total_encounters=summary.total_encounters,
        queue_size=summary.queue_size,
        queue_share_of_encounters=analysis.queue_share_of_encounters,
        high_risk_count=summary.high_risk,
        high_risk_readmission_rate=high_group.readmission_rate,
        baseline_readmission_rate=analysis.baseline_readmission_rate,
        high_risk_lift=analysis.high_risk_lift,
        queue_capture_of_readmissions=analysis.queue_capture_of_readmissions,
        interventions_by_status={s.value: by_status.get(s.value, 0) for s in STATUS_ORDER},
        closure_rate=_rate(summary.completed_interventions, summary.queue_size),
    )