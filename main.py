from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime
import json
from typing import List

# Import semantic mapping logic from the LLM service module
from llm_service import translate_symptoms_to_medical_terms

# Load environment variables for secure database credential management
load_dotenv()

# Pydantic model for structured user side-effect reporting
class SideEffectReport(BaseModel):
    drug_name: str
    symptom: str

# Database connection configuration using PostgreSQL-specific URI
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@localhost:5433/{os.getenv('DB_NAME')}"

# Initialize the SQLAlchemy engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="MediMatch AI Backend")

# Dependency: Injects a database session into route handlers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Ensures the connection is returned to the pool after the request
        db.close()

# --- BASIC ENDPOINTS (HEALTH & DATA LOOKUP) ---

@app.get("/health-check")
def health_check(db: Session = Depends(get_db)):
    """Verifies database connectivity and returns the total drug record count."""
    try:
        count = db.execute(text("SELECT COUNT(*) FROM drugs")).scalar()
        return {"status": "success", "total_drugs": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze-symptoms")
def analyze_symptoms(query: str, db: Session = Depends(get_db)):
    """
    Reverse Lookup Module: 
    1. Uses LLM to extract clinical terms from natural language.
    2. Performs an ILIKE search against mapped drug side effects.
    3. Logs the search history for audit purposes.
    """
    # Persistence: Log search activity in user_logs table
    log_entry = json.dumps({"search_query": query, "timestamp": str(datetime.now())})
    db.execute(
        text("INSERT INTO user_logs (query_type, input_text, result_data) VALUES (:q, :i, :r)"),
        {"q": "SEARCH_ACCESS", "i": query, "r": log_entry}
    )
    db.commit()
    
    # Semantic processing via OpenAI API
    medical_terms = translate_symptoms_to_medical_terms(query)
    
    search_results = []
    for term in medical_terms:
        # SQL logic: Joins drugs with side effects via mapping table
        sql = text("""
            SELECT DISTINCT TRIM(BOTH '''' FROM d.common_name) as drug_name, se.se_name
            FROM drug_side_effects dse
            JOIN drugs d ON dse.drug_id = d.stitch_id
            JOIN side_effects se ON dse.se_code = se.se_code
            WHERE se.se_name ILIKE :term
            LIMIT 5
        """)
        rows = db.execute(sql, {"term": f"%{term}%"}).fetchall()
        for row in rows:
            search_results.append({"drug": row[0], "side_effect": row[1]})

    return {
        "user_query": query, 
        "semantic_matches": medical_terms, 
        "possible_drugs": search_results
    }

@app.get("/drug-effects")
def get_drug_effects(name: str, db: Session = Depends(get_db)):
    """Direct Lookup: Retrieves known side effects for a specific drug name using pattern matching."""
    sql = text("""
        SELECT DISTINCT se.se_name
        FROM side_effects se
        JOIN drug_side_effects dse ON se.se_code = dse.se_code
        JOIN drugs d ON dse.drug_id = d.stitch_id
        WHERE d.common_name ILIKE :name
        LIMIT 15
    """)
    results = db.execute(sql, {"name": f"%{name.strip()}%"}).fetchall()
    return {"side_effects": [r[0] for r in results]}

@app.post("/report-side-effect")
def report_side_effect(report: SideEffectReport, db: Session = Depends(get_db)):
    """Persists user-generated side effect reports in the history log (Audit Trail)."""
    # Validation: Ensure the medication exists in the primary catalog
    query = text("SELECT stitch_id, common_name FROM drugs WHERE TRIM(BOTH '''' FROM common_name) ILIKE :name")
    drug = db.execute(query, {"name": f"%{report.drug_name}%"}).fetchone()
    
    if not drug:
        raise HTTPException(status_code=404, detail=f"Medication '{report.drug_name}' not found.")

    try:
        log_entry = json.dumps({"drug_name": report.drug_name, "reported_symptom": report.symptom})
        db.execute(
            text("INSERT INTO user_logs (query_type, input_text, result_data) VALUES ('SIDE_EFFECT_REPORT', :i, :r)"),
            {"i": report.drug_name, "r": log_entry}
        )
        db.commit() 
        return {"status": "success", "message": "Report saved successfully."}
    except Exception as e:
        db.rollback() # Maintain atomicity
        raise HTTPException(status_code=500, detail="Internal database error.")

# --- SCIENTIFIC ANALYSIS ENDPOINTS (DATA MINING) ---

@app.get("/science/top-target-correlations")
def get_top_correlations(db: Session = Depends(get_db)):
    """
    Performance Optimization: Retrieves aggregated protein-target correlations 
    pre-calculated in a Materialized View (mv_target_correlations).
    """
    try:
        sql = text("""
            SELECT protein_id, se_name, drug_count 
            FROM mv_target_correlations 
            ORDER BY drug_count DESC 
            LIMIT 25
        """)
        results = db.execute(sql).fetchall()
        
        if not results:
            return []
            
        return [
            {"protein_id": str(r[0]), "side_effect": r[1], "drug_count": r[2]} 
            for r in results
        ]
    except Exception as e:
        # Error likely indicates that the Materialized View has not been initialized
        print(f"Scientific Analysis Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Materialized view missing or unrefreshed.")

@app.get("/science/target-drugs")
def get_target_drugs(protein_id: str, side_effect: str, db: Session = Depends(get_db)):
    """
    Drill-down Analysis: Executes a complex JOIN to resolve the individual 
    drug entities associated with a specific protein/symptom pair.
    """
    try:
        sql = text("""
            SELECT DISTINCT TRIM(BOTH '''' FROM d.common_name) as drug_name
            FROM drug_targets dt
            JOIN drugs d ON dt.drug_id = d.stitch_id
            JOIN drug_side_effects dse ON d.stitch_id = dse.drug_id
            JOIN side_effects se ON dse.se_code = se.se_code
            WHERE CAST(dt.protein_id AS TEXT) = :p_id 
              AND se.se_name = :se_name
        """)
        results = db.execute(sql, {"p_id": str(protein_id), "se_name": side_effect}).fetchall()
        return {"drugs": [r[0] for r in results]}
    except Exception as e:
        print(f"Drill-down Resolution Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error during drill-down resolution.")