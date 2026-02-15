# MediMatch AI: Clinical Analysis & Reporting System

**MediMatch AI** is a web-based DBMS project designed to analyze medication side effects and protein-target interactions. The system processes over 4 million records (based on SIDER, STITCH, and SNAP datasets) and utilizes LLM integration for semantic search queries.

---

## Core Features (Requirement Mapping)

| Requirement | Implementation in System |
| :--- | :--- |
| **Symptom Search (Reverse Lookup)** | AI-powered extraction of medical terminology from natural language to identify potential medications. |
| **Direct Query (Drug Selection)** | Retrieval of all known side effects for specific medications directly from the database. |
| **User Reporting** | Interface for reporting new side effects, which are stored persistently in the database (`user_logs`) for clinical audit. |
| **Historization (Audit Trail)** | Every search query and data access is automatically recorded in an audit log with timestamps and metadata. |
| **Scientific Analysis** | Advanced SQL module for correlating protein-target bindings with shared side-effect profiles. |
| **Semantic Interoperability** | Integration of the OpenAI GPT-4o API to bridge the gap between patient language and formal medical nomenclature. |

---

## Technical Stack

* **Frontend:** **Streamlit** (Python) – Modern, reactive framework for data-centric web applications.
* **Backend:** **FastAPI** (Python) – High-performance asynchronous API architecture.
* **Database:** **PostgreSQL** – Management of >4 million records with high-performance indexing.
* **AI Integration:** **OpenAI API** – Semantic mapping and natural language processing.
* **ORM/SQL:** **SQLAlchemy** – Robust database abstraction and transaction management.



---

## Database Architecture & Performance

The system integrates complex clinical datasets across three core layers:

1. **Chemical-Symptom Mapping:** Linking active substances to documented side effects (Monotherapy & Combination).
2. **Biological-Target Mapping:** Associating medications with specific biological proteins.
3. **Flexible Audit Logging:** JSONB-based storage in `user_logs` to capture diverse interaction metadata without schema rigidity.



### Optimizations for Big Data (4M+ Rows)
To achieve sub-100ms response times for a multi-million row dataset, several optimization strategies were implemented:

* **Indexing Strategy:** B-Tree indices on all foreign key columns (`drug_id`, `se_code`, `protein_id`) to optimize JOIN operations.
* **Materialized Views:** Precomputed aggregations (`mv_target_correlations`) store complex calculations for the scientific dashboard, eliminating the need for intensive live JOINs.
* **Search Optimization:** Use of `ILIKE` combined with in-memory string normalization to handle data cleaning during runtime.

---

## Scientific Module: Protein-Target Analysis

The system provides a technical environment to investigate a central clinical hypothesis:
> *"Do medications that bind to the same proteins exhibit statistically significant similarities in their side-effect profiles?"*

The module utilizes a **Drill-Down Analysis** pattern. Users can select specific Protein-Target correlations to reveal the underlying drug entities. This is achieved through complex SQL JOINs across the pharmaceutical and biological data layers.

---

## Installation & Setup

To run the application, ensure both the backend and frontend are active simultaneously in separate terminal sessions.

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/Fabi0704/DBMS_drug_side_effects.git](https://github.com/Fabi0704/DBMS_drug_side_effects.git)
   cd DBMS_drug_side_effects

2. **Virtual Environment & Dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. **Environment Variables:**
    Create a `.env` file containing your database string and OpenAI key:
    ```env
    DATABASE_URL=postgresql://user:password@localhost:5433/dbname
    OPENAI_API_KEY=your_api_key_here
    ```

4. **Execution (Dual-Terminal Setup):**
    ```bash
    fastapi dev main.py
    streamlit run app.py
    ```

---

## License
This project was developed as part of the **Database Management Systems (DBMS)** module during the Winter Semester 2025/26.