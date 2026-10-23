from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from src import service
from src.database import open_pool, close_pool
from src.models import (
    EncounterOut, EncounterList, CareQueueList, InterventionOut, InterventionUpdate,
    OperationsSummary, ReadmissionAnalysis, ManagementDashboard, ErrorResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()        # runs once at startup
    yield              # app serves requests here
    close_pool()       # runs once at shutdown


app = FastAPI(title="Diabetes Readmission Intervention Queue", lifespan=lifespan)


ERROR_STATUS = {
    service.EncounterNotFound: 404,
    service.NotInCareQueue: 409,
    service.InvalidStatusTransition: 409,
}


@app.exception_handler(service.DomainError)
async def domain_error_handler(request: Request, exc: service.DomainError):
    return JSONResponse(
        status_code=ERROR_STATUS.get(type(exc), 400),
        content={"detail": str(exc)},
    )

NOT_FOUND = {404: {"model": ErrorResponse}}
CONFLICT = {409: {"model": ErrorResponse}}


@app.get("/encounters", response_model=EncounterList)
def list_encounters(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return service.list_encounters(limit, offset)


@app.get("/encounters/{encounter_id}", response_model=EncounterOut, responses=NOT_FOUND)
def get_encounter(encounter_id: int):
    return service.get_encounter(encounter_id)


@app.get("/care-queue", response_model=CareQueueList)
def get_care_queue(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    return service.get_care_queue(limit, offset)


# TODO: GET /care-queue/high → service.get_high_risk_queue  (same shape as above)


@app.patch(
    "/interventions/{encounter_id}",
    response_model=InterventionOut,
    responses={**NOT_FOUND, **CONFLICT},
)
def update_intervention(encounter_id: int, update: InterventionUpdate):
    return service.update_intervention(encounter_id, update)


# TODO: GET /operations/summary              → OperationsSummary
# TODO: GET /operations/readmission-analysis → ReadmissionAnalysis
# TODO: GET /management/dashboard            → ManagementDashboard

@app.get("/operations/summary", response_model=OperationsSummary)
def get_operations_summary():
    return service.get_operations_summary()

@app.get("/operations/readmission-analysis", response_model=ReadmissionAnalysis)
def get_readmission_analysis():
    return service.get_readmission_analysis()

@app.get("/management/dashboard", response_model=ManagementDashboard)
def get_management_dashboard():
    return service.get_management_dashboard()