from tkinter.constants import S
from typing import Any


import pandas as pd
import os
from dotenv import load_dotenv

from src import service   
from src.database import open_pool, close_pool, get_connection
from src.repository import bulk_insert_encounters

load_dotenv()
CSV_PATH = os.getenv("CSV_PATH")
if not CSV_PATH:
    raise RuntimeError("CSV_PATH is not set (check .env)")



# 1. Same order as the INSERT columns
COLUMNS = [
    "encounter_id", "patient_nbr", "age", "time_in_hospital",
    "number_inpatient", "number_emergency", "number_outpatient",
    "num_medications", "num_lab_procedures",
    "discharge_disposition_id", "admission_type_id", "readmitted",
]
VALID_READMITTED = {"NO", ">30", "<30"}




def load_and_clean(path):
 # 2. read only COLUMNS, treat "?" as missing      → pd.read_csv(..., usecols=..., na_values="?")
    # 3. put the columns in COLUMNS order              → df = df[COLUMNS]
    # 4. drop rows with missing values                 → dropna
    # 5. drop duplicate encounter_id                   → drop_duplicates(subset=...)
    # 6. keep only valid readmitted values             → df[df["readmitted"].isin(...)]

    df = pd.read_csv(path, usecols=COLUMNS, na_values="?")
    df = df[COLUMNS]
    df = df.dropna()
    df = df.drop_duplicates(subset=["encounter_id"])
    df = df[df["readmitted"].isin(VALID_READMITTED)]
    return df

def to_rows(df):
	# 7. numpy types → plain Python types (the trap!)
	df = df.astype(object).where(pd.notna(df), None) # convert numpy types to plain Python types
	return list(df.itertuples(index=False))

def main():
    df = load_and_clean(CSV_PATH)
    rows = to_rows(df)
    print(f"Rows after cleaning: {len(rows)}")
    open_pool()
    try:
        with get_connection() as conn:
            inserted = bulk_insert_encounters(conn, rows)
            print(f"Inserted: {inserted}")
        scored = service.score_all_encounters()
        print(f"Scored: {scored}")
        queued = service.build_care_queue()
        print(f"Queued: {queued}")
    finally:
        close_pool()

if __name__ == "__main__":
    main()
