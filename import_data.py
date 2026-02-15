import os
import tarfile
import pandas as pd
import requests
import io
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables for database credentials
load_dotenv()

# Database connection setup using SQLAlchemy
# The connection string targets the PostgreSQL instance running on port 5433
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@localhost:5433/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)

def is_table_empty(table_name):
    """
    Utility function to check if a specific table already contains data.
    This prevents duplicate imports and allows for idempotent script execution.
    """
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
        return count == 0

def download_and_extract_gz(url):
    """
    Handles the remote fetching and in-memory extraction of .tar.gz archives.
    Includes a filter to ignore macOS metadata files (._) that can corrupt dataframes.
    """
    print(f"Downloading data from {url}...")
    response = requests.get(url)
    
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
        # Filter: Ignoring hidden macOS metadata files and system artifacts
        members = [
            m for m in tar.getmembers() 
            if m.isfile() and not os.path.basename(m.name).startswith('._')
        ]
        
        if not members:
            print("No valid data file found in the archive!")
            return None
        
        # Select the primary data member for extraction
        target_file = members[0]
        print(f"Extracting data file: {target_file.name}")
        
        # Stream the extracted file directly into a pandas DataFrame
        # 'latin1' encoding ensures compatibility with legacy dataset formatting
        df = pd.read_csv(tar.extractfile(target_file), sep=',', encoding='latin1')
        
        # Data Cleaning: Remove leading/trailing whitespaces from headers
        df.columns = df.columns.str.strip()
        return df

def import_phase_1_names():
    """
    Phase 1: Imports the core drug catalog.
    This establishes the foreign key references for all subsequent import phases.
    """
    if not is_table_empty('drugs'):
        print("Phase 1 skipped: 'drugs' table is already populated.")
        return

    print("--- Phase 1: Drug Names ---")
    names_url = "https://www.pingzhang.net/bak/ddi/drug_569.txt"
    
    # Load dataset using tab separation as per the source format
    df_names = pd.read_csv(names_url, sep='\t', names=['stitch_id', 'common_name'])
    
    # Pre-import Cleaning: Removing duplicate stitch_id entries to maintain primary key integrity
    df_names = df_names.drop_duplicates(subset=['stitch_id'], keep='first')
    
    print(f"Processing data: {len(df_names)} unique drugs identified.")
    df_names.to_sql('drugs', engine, if_exists='append', index=False)
    print("Phase 1 successful.")

def import_phase_2_mono():
    """
    Phase 2: Imports monotherapy side effects.
    Initializes the 'side_effects' catalog and maps initial drug relationships.
    """
    if not is_table_empty('side_effects'):
        print("Phase 2 skipped: 'side_effects' table is already populated.")
        return

    print("\n--- Phase 2: Side Effects (Mono) ---")
    mono_url = "http://snap.stanford.edu/decagon/bio-decagon-mono.tar.gz"
    df_mono = download_and_extract_gz(mono_url)

    try:
        col_stitch = df_mono.columns[0]
        col_se_id = df_mono.columns[1]
        col_se_name = df_mono.columns[2]
        
        # 1. Populate the side effect master catalog
        se_catalog = df_mono[[col_se_id, col_se_name]].drop_duplicates(subset=[col_se_id])
        se_catalog.columns = ['se_code', 'se_name']
        se_catalog.to_sql('side_effects', engine, if_exists='append', index=False)
        print(f"{len(se_catalog)} side effects imported into the catalog.")

        # 2. Map drug-symptom relationships with data normalization
        drug_se = df_mono[[col_stitch, col_se_id]].copy()
        drug_se.columns = ['drug_id', 'se_code']
        
        # Normalization: Removing SQL-sensitive characters like single quotes
        drug_se['drug_id'] = drug_se['drug_id'].astype(str).str.replace("'", "").str.strip()
        
        with engine.connect() as conn:
            # Cross-reference against existing drugs in the database
            existing_ids = pd.read_sql("SELECT stitch_id FROM drugs", conn)['stitch_id'].values
            existing_ids = [str(x).replace("'", "").strip() for x in existing_ids]
        
        # Filtering: Ensuring referential integrity by only importing known drugs
        drug_se_filtered = drug_se[drug_se['drug_id'].isin(existing_ids)]
        
        if len(drug_se_filtered) > 0:
            print(f"Validation successful: {len(drug_se_filtered)} mappings matched.")
            drug_se_filtered.to_sql('drug_side_effects', engine, if_exists='append', index=False, chunksize=1000)
            print("Phase 2 completed.")
            
    except Exception as e:
        print(f"Data processing error in Phase 2: {e}")

def import_phase_3_combo():
    """
    Phase 3: Imports combination therapy (interaction) side effects.
    Updates the catalog with new side effects found in the combination dataset.
    """
    print("\n--- Phase 3: Interactions (Combo) ---")
    combo_url = "http://snap.stanford.edu/decagon/bio-decagon-combo.tar.gz"
    df_combo = download_and_extract_gz(combo_url)

    col_d1, col_d2, col_se_id, col_se_name = df_combo.columns[0], df_combo.columns[1], df_combo.columns[2], df_combo.columns[3]

    with engine.connect() as conn:
        existing_drugs = set(pd.read_sql("SELECT stitch_id FROM drugs", conn)['stitch_id'].str.replace("'", "").str.strip().values)
        existing_se = set(pd.read_sql("SELECT se_code FROM side_effects", conn)['se_code'].values)

    # Normalization of drug identifiers
    df_combo[col_d1] = df_combo[col_d1].astype(str).str.replace("'", "").str.strip()
    df_combo[col_d2] = df_combo[col_d2].astype(str).str.replace("'", "").str.strip()

    # Filter: Only process entries where both drugs exist in our master 'drugs' table
    df_filtered = df_combo[df_combo[col_d1].isin(existing_drugs) & df_combo[col_d2].isin(existing_drugs)]
    print(f"Identified {len(df_filtered)} relevant combination entries.")

    # Update side effect catalog with terms unique to combination therapy
    new_se = df_filtered[[col_se_id, col_se_name]].drop_duplicates(subset=[col_se_id])
    new_se.columns = ['se_code', 'se_name']
    
    new_se_to_add = new_se[~new_se['se_code'].isin(existing_se)]
    if not new_se_to_add.empty:
        new_se_to_add.to_sql('side_effects', engine, if_exists='append', index=False)
        print(f"Updated catalog with {len(new_se_to_add)} new side effect terms.")

    # Flatten the combination mapping for the drug_side_effects table
    # This records the side effect for both individual drugs involved in the combo
    combo_rows = pd.concat([
        df_filtered[[col_d1, col_se_id]].rename(columns={col_d1: 'drug_id', col_se_id: 'se_code'}),
        df_filtered[[col_d2, col_se_id]].rename(columns={col_d2: 'drug_id', col_se_id: 'se_code'})
    ]).drop_duplicates()
    
    combo_rows['is_combo'] = True
    combo_rows.to_sql('drug_side_effects', engine, if_exists='append', index=False, chunksize=1000)
    print("Phase 3 successfully completed.")

def import_phase_4_targets():
    """
    Phase 4: Imports drug-protein target interactions.
    Links the chemical entities to biological targets for scientific analysis.
    """
    print("\n--- Phase 4: Protein Targets ---")
    targets_url = "http://snap.stanford.edu/decagon/bio-decagon-targets.tar.gz"
    df_targets = download_and_extract_gz(targets_url)
    
    col_drug = df_targets.columns[0]
    col_target = df_targets.columns[1]

    with engine.connect() as conn:
        existing_drugs = set(pd.read_sql("SELECT stitch_id FROM drugs", conn)['stitch_id'].str.replace("'", "").str.strip().values)

    df_targets[col_drug] = df_targets[col_drug].astype(str).str.replace("'", "").str.strip()
    df_filtered = df_targets[df_targets[col_drug].isin(existing_drugs)].drop_duplicates()
    
    df_filtered.columns = ['drug_id', 'protein_id']
    df_filtered.to_sql('drug_targets', engine, if_exists='append', index=False)
    print(f"Imported {len(df_filtered)} drug-protein target mappings.")

# Orchestration of the ETL pipeline
if __name__ == "__main__":
    import_phase_1_names()
    import_phase_2_mono()
    import_phase_3_combo()
    import_phase_4_targets()