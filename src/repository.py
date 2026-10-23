def bulk_insert_encounters(conn, rows):
    sql = """
        INSERT INTO patient_encounters (
            encounter_id, patient_nbr, age, time_in_hospital,
            number_inpatient, number_emergency, number_outpatient,
            num_medications, num_lab_procedures,
            discharge_disposition_id, admission_type_id, readmitted
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (encounter_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        return cur.rowcount

def fetch_scoring_inputs(conn):
    sql = """
        SELECT encounter_id, number_inpatient, number_emergency,
               number_outpatient, time_in_hospital, num_medications
        FROM patient_encounters
    """
    return conn.execute(sql).fetchall()

def bulk_update_scores(conn, rows):
    # rows = [(score, level, encounter_id), ...]
    # TODO: same pattern as bulk_insert_encounters:
    #   sql = "UPDATE patient_encounters SET risk_score = %s, risk_level = %s WHERE encounter_id = %s"
    #   cursor → executemany → return rowcount
    sql = "UPDATE patient_encounters SET risk_score = %s, risk_level = %s WHERE encounter_id = %s"
    rows = [(score, level, encounter_id) for score, level, encounter_id in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        return cur.rowcount

def populate_queue(conn):
    sql = """
        INSERT INTO care_interventions (encounter_id)
        SELECT encounter_id
        FROM patient_encounters
        WHERE risk_level IN ('MEDIUM', 'HIGH')
        ON CONFLICT (encounter_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.rowcount

def count_encounters(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM patient_encounters").fetchone()["n"]

def list_encounters(conn, limit, offset):
    sql = """
        SELECT * FROM patient_encounters
        ORDER BY encounter_id
        LIMIT %s OFFSET %s
    """
    return conn.execute(sql, (limit, offset)).fetchall()

def get_encounter(conn, encounter_id):
    # TODO: SELECT * ... WHERE encounter_id = %s ; use .fetchone()
    #       (fetchone returns None when no row matches — the service relies on that)
    sql = """
        SELECT * FROM patient_encounters
        WHERE encounter_id = %s
    """
    return conn.execute(sql, (encounter_id,)).fetchone()

QUEUE_COLUMNS = """
    e.encounter_id, e.patient_nbr, e.age, e.risk_score, e.risk_level,
    e.number_inpatient, e.number_emergency, e.number_outpatient,
    e.time_in_hospital, e.num_medications,
    i.status, i.assigned_to, i.notes, i.updated_at
"""

def get_care_queue(conn, levels, limit, offset):
    sql = f"""
        SELECT {QUEUE_COLUMNS}
        FROM patient_encounters e
        JOIN care_interventions i ON i.encounter_id = e.encounter_id
        WHERE e.risk_level = ANY(%s)
        ORDER BY e.risk_score DESC, e.number_inpatient DESC, e.encounter_id
        LIMIT %s OFFSET %s
    """
    return conn.execute(sql, (levels, limit, offset)).fetchall()

def count_care_queue(conn, levels):
    # TODO: SELECT COUNT(*) AS n with the same FROM / JOIN / WHERE (no ORDER BY / LIMIT)
    sql = f"""
        SELECT COUNT(*) AS n
        FROM patient_encounters e
        JOIN care_interventions i ON i.encounter_id = e.encounter_id
        WHERE e.risk_level = ANY(%s)
    """
    return conn.execute(sql, (levels,)).fetchone()["n"]

UPDATABLE_COLUMNS = {"status", "assigned_to", "notes"}

def get_intervention(conn, encounter_id):
    sql = "SELECT * FROM care_interventions WHERE encounter_id = %s"
    return conn.execute(sql, (encounter_id,)).fetchone()

def update_intervention(conn, encounter_id, fields):
    unknown = set(fields) - UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Cannot update columns: {unknown}")

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    sql = f"""
        UPDATE care_interventions
        SET {set_clause}
        WHERE encounter_id = %s
        RETURNING *
    """
    params = [*fields.values(), encounter_id]
    return conn.execute(sql, params).fetchone()

def count_by_risk_level(conn):
    sql = "SELECT risk_level, COUNT(*) AS n FROM patient_encounters GROUP BY risk_level"
    rows = conn.execute(sql).fetchall()
    return {r["risk_level"]: r["n"] for r in rows}
    # → {"HIGH": 2358, "MEDIUM": 6180, "LOW": 93228}   (None key = unscored, if any)

def count_interventions_by_status(conn):
    # TODO: same pattern on care_interventions, GROUP BY status
    # → {"PENDING_REVIEW": 8537, "ASSIGNED": 1}
    sql = "SELECT status, COUNT(*) AS n FROM care_interventions GROUP BY status"
    rows = conn.execute(sql).fetchall()
    return {r["status"]: r["n"] for r in rows}

def readmission_by_risk_level(conn):
    sql = """
        SELECT risk_level,
               COUNT(*) AS encounters,
               COUNT(*) FILTER (WHERE readmitted = '<30') AS readmitted_under_30
        FROM patient_encounters
        WHERE risk_level IS NOT NULL
        GROUP BY risk_level
    """
    return conn.execute(sql).fetchall()

