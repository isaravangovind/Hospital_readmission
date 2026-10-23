from pydantic import BaseModel, Field, StringConstraints
from datetime import datetime
from typing import Optional, Annotated

from enum import Enum

AssignedTo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class InterventionStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ASSIGNED = "ASSIGNED"
    CONTACTED = "CONTACTED"
    FOLLOW_UP_SCHEDULED = "FOLLOW_UP_SCHEDULED"
    CLOSED = "CLOSED"

# lifecycle order, used later for the forward-only rule (D2)
STATUS_ORDER = (
    InterventionStatus.PENDING_REVIEW,
    InterventionStatus.ASSIGNED,
    InterventionStatus.CONTACTED,
    InterventionStatus.FOLLOW_UP_SCHEDULED,
    InterventionStatus.CLOSED,
)

from typing import Annotated, Optional
from pydantic import BaseModel, StringConstraints, model_validator

AssignedTo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

class InterventionUpdate(BaseModel):
    status: Optional[InterventionStatus] = None
    assigned_to: Optional[AssignedTo] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def check_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one of: status, assigned_to, notes")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self




# ---------- Table A: patient_encounters ----------

class EncounterOut(BaseModel):
    encounter_id: int = Field(..., description="Unique encounter ID")
    patient_nbr: int = Field(..., description="Patient number (can repeat across encounters)")
    age: str = Field(..., description="Age bucket, e.g. [70-80)")
    time_in_hospital: int = Field(..., description="Days in hospital")
    number_inpatient: int = Field(..., description="Inpatient visits in prior year")
    number_emergency: int = Field(..., description="Emergency visits in prior year")
    number_outpatient: int = Field(..., description="Outpatient visits in prior year")
    num_medications: int = Field(..., description="Number of medications")
    num_lab_procedures: int = Field(..., description="Number of lab procedures")
    discharge_disposition_id: Optional[int] = Field(None, description="Discharge disposition code")
    admission_type_id: Optional[int] = Field(None, description="Admission type code")
    readmitted: str = Field(..., description="Historical outcome: NO, <30, >30")
    risk_score: Optional[int] = Field(None, description="Rule-based risk score (0-8)")
    risk_level: Optional[str] = Field(None, description="LOW, MEDIUM or HIGH")


class EncounterList(BaseModel):
    items: list[EncounterOut] = Field(..., description="Encounters on this page")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Rows skipped")
    total: int = Field(..., description="Total encounters")


# ---------- Care queue (Table A joined with Table B) ----------

class CareQueueItem(BaseModel):
    encounter_id: int = Field(..., description="Unique encounter ID")
    patient_nbr: int = Field(..., description="Patient number")
    age: str = Field(..., description="Age bucket")
    risk_score: int = Field(..., description="Rule-based risk score")
    risk_level: str = Field(..., description="MEDIUM or HIGH")
    number_inpatient: int = Field(..., description="Inpatient visits in prior year")
    number_emergency: int = Field(..., description="Emergency visits in prior year")
    number_outpatient: int = Field(..., description="Outpatient visits in prior year")
    time_in_hospital: int = Field(..., description="Days in hospital")
    num_medications: int = Field(..., description="Number of medications")
    status: str = Field(..., description="Intervention status")
    assigned_to: Optional[str] = Field(None, description="Care coordinator name")
    notes: Optional[str] = Field(None, description="Free-text notes")
    updated_at: datetime = Field(..., description="Last update time")
    risk_reasons: list[str] = Field(default_factory=list, description="Which risk rules fired")


class CareQueueList(BaseModel):
    items: list[CareQueueItem] = Field(..., description="Queue items on this page")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Rows skipped")
    total: int = Field(..., description="Total items in queue")


# ---------- Table B: care_interventions ----------

class InterventionOut(BaseModel):
    intervention_id: int = Field(..., description="Unique intervention ID")
    encounter_id: int = Field(..., description="Linked encounter ID")
    status: str = Field(..., description="Intervention status")
    assigned_to: Optional[str] = Field(None, description="Care coordinator name")
    notes: Optional[str] = Field(None, description="Free-text notes")
    created_at: datetime = Field(..., description="Created time")
    updated_at: datetime = Field(..., description="Last update time")


# ---------- Metrics ----------

class OperationsSummary(BaseModel):
    total_encounters: int = Field(..., description="All encounters")
    high_risk: int = Field(..., description="HIGH risk encounters")
    medium_risk: int = Field(..., description="MEDIUM risk encounters")
    low_risk: int = Field(..., description="LOW risk encounters")
    unscored: int = Field(..., description="Encounters without a score")
    queue_size: int = Field(..., description="MEDIUM + HIGH encounters")
    pending_interventions: int = Field(..., description="Status PENDING_REVIEW")
    in_progress_interventions: int = Field(..., description="ASSIGNED + CONTACTED + FOLLOW_UP_SCHEDULED")
    completed_interventions: int = Field(..., description="Status CLOSED")


class RiskGroupOutcome(BaseModel):
    risk_level: str = Field(..., description="LOW, MEDIUM or HIGH")
    encounters: int = Field(..., description="Encounters in this group")
    readmitted_under_30_days: int = Field(..., description="Encounters readmitted <30 days")
    readmission_rate: float = Field(..., description="Percent readmitted <30 days")


class ReadmissionAnalysis(BaseModel):
    baseline_encounters: int = Field(..., description="All scored encounters")
    baseline_readmitted_under_30_days: int = Field(..., description="All scored encounters readmitted <30")
    baseline_readmission_rate: float = Field(..., description="Overall <30 readmission percent")
    groups: list[RiskGroupOutcome] = Field(..., description="Outcome per risk level")
    high_risk_lift: float = Field(..., description="HIGH rate / baseline rate")
    queue_share_of_encounters: float = Field(..., description="Percent of encounters in queue")
    queue_capture_of_readmissions: float = Field(..., description="Percent of <30 readmissions in queue")


class ManagementDashboard(BaseModel):
    total_encounters: int = Field(..., description="All encounters")
    queue_size: int = Field(..., description="MEDIUM + HIGH encounters")
    queue_share_of_encounters: float = Field(..., description="Percent of encounters in queue")
    high_risk_count: int = Field(..., description="HIGH risk encounters")
    high_risk_readmission_rate: float = Field(..., description="HIGH group <30 readmission percent")
    baseline_readmission_rate: float = Field(..., description="Overall <30 readmission percent")
    high_risk_lift: float = Field(..., description="HIGH rate / baseline rate")
    queue_capture_of_readmissions: float = Field(..., description="Percent of <30 readmissions in queue")
    interventions_by_status: dict[str, int] = Field(..., description="Count per status")
    closure_rate: float = Field(..., description="Percent of queue CLOSED")
    disclaimer: str = Field(
        "Learning prototype — not for clinical decision-making",
        description="Fixed disclaimer",
    )


# ---------- Errors ----------

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")