-- schema.sql
-- Diabetes Readmission Intervention Queue — learning prototype only.
-- Safe to re-run: uses IF NOT EXISTS / CREATE OR REPLACE.

-- Table A: one row per hospital encounter (loaded from CSV, then scored)
CREATE TABLE IF NOT EXISTS patient_encounters (
    encounter_id              BIGINT       PRIMARY KEY,
    patient_nbr               BIGINT       NOT NULL,
    age                       VARCHAR(10)  NOT NULL,
    time_in_hospital          SMALLINT     NOT NULL CHECK (time_in_hospital >= 0),
    number_inpatient          SMALLINT     NOT NULL DEFAULT 0 CHECK (number_inpatient >= 0),
    number_emergency          SMALLINT     NOT NULL DEFAULT 0 CHECK (number_emergency >= 0),
    number_outpatient         SMALLINT     NOT NULL DEFAULT 0 CHECK (number_outpatient >= 0),
    num_medications           SMALLINT     NOT NULL CHECK (num_medications >= 0),
    num_lab_procedures        SMALLINT     NOT NULL CHECK (num_lab_procedures >= 0),
    discharge_disposition_id  SMALLINT,
    admission_type_id         SMALLINT,
    readmitted                VARCHAR(5)   NOT NULL CHECK (readmitted IN ('NO', '<30', '>30')),
    risk_score                SMALLINT     CHECK (risk_score BETWEEN 0 AND 8),
    risk_level                VARCHAR(10)  CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT chk_risk_pair CHECK (
        (risk_score IS NULL AND risk_level IS NULL) OR
        (risk_score IS NOT NULL AND risk_level IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_encounters_risk_level  ON patient_encounters (risk_level, risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_encounters_patient_nbr ON patient_encounters (patient_nbr);

-- Table B: one intervention per MEDIUM/HIGH-risk encounter (the care queue)
CREATE TABLE IF NOT EXISTS care_interventions (
    intervention_id  BIGSERIAL    PRIMARY KEY,
    encounter_id     BIGINT       NOT NULL UNIQUE
                     REFERENCES patient_encounters (encounter_id) ON DELETE CASCADE,
    status           VARCHAR(25)  NOT NULL DEFAULT 'PENDING_REVIEW'
                     CHECK (status IN ('PENDING_REVIEW','ASSIGNED','CONTACTED','FOLLOW_UP_SCHEDULED','CLOSED')),
    assigned_to      VARCHAR(100),
    notes            TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interventions_status ON care_interventions (status);

-- Keep updated_at current on every UPDATE
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_care_interventions_updated_at ON care_interventions;
CREATE TRIGGER trg_care_interventions_updated_at
    BEFORE UPDATE ON care_interventions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();