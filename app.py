import streamlit as st
import requests
import pandas as pd

# Page configuration for the Streamlit web interface
# Note: Emojis have been removed from page_icon and titles as requested
st.set_page_config(
    page_title="MediMatch AI Portal",
    page_icon=None,
    layout="wide"
)

# Configuration for the FastAPI backend connection
# This URL points to the local uvicorn server running the FastAPI application
BASE_URL = "http://127.0.0.1:8000"

# --- CACHING FUNCTIONS ---
@st.cache_data
def fetch_correlation_data():
    """
    Fetches and caches the scientific correlation data from the Materialized View.
    Caching prevents redundant API calls and maintains UI stability during reruns.
    """
    try:
        response = requests.get(f"{BASE_URL}/science/top-target-correlations")
        if response.status_code == 200:
            return response.json()
    except Exception:
        # Returns None if the backend is unreachable or the request fails
        return None
    return None

# --- UI MAIN HEADER ---
st.title("MediMatch AI Portal")
st.markdown("### Clinical Decision Support System for Medication Side Effects")

# Sidebar Navigation logic
st.sidebar.title("Navigation")
menu = ["Home & Search", "Report Side Effect", "Scientific Analysis"]
choice = st.sidebar.selectbox("Go to:", menu)

# --- SECTION 1: HOME & SEARCH (Symptom and Drug Lookups) ---
if choice == "Home & Search":
    col1, col2 = st.columns(2)

    # Column 1: AI-powered Symptom Analysis (Reverse Lookup)
    with col1:
        st.header("Symptom Analysis")
        st.caption("Describe symptoms in natural language to find possible drug causes via LLM mapping")
        
        symptom_query = st.text_input(
            "Enter symptoms", 
            placeholder="e.g., I have a severe headache and feel dizzy"
        )
        
        if st.button("Start AI Analysis"):
            if symptom_query:
                with st.spinner("Analyzing symptoms and searching database..."):
                    try:
                        # Sending query to the FastAPI endpoint for LLM semantic mapping
                        response = requests.get(
                            f"{BASE_URL}/analyze-symptoms", 
                            params={"query": symptom_query}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            if data.get("possible_drugs"):
                                st.markdown("---")
                                st.subheader("Based on the description, here are drugs impacting these symptoms:")
                                
                                for item in data["possible_drugs"]:
                                    # String cleaning logic to handle SQL formatting artifacts
                                    clean_drug_name = item['drug'].replace("'", "")
                                    st.markdown(f"**Drug:** {clean_drug_name}")
                                    st.markdown(f"**Side Effect match:** {item['side_effect']}")
                                    st.write("") 
                            else:
                                st.info("No direct matches found in the database for this description.")
                        else:
                            st.error(f"Backend error: {response.status_code}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("Connection Error: Is the FastAPI backend running on port 8000?")
            else:
                st.warning("Please provide a description of your symptoms.")

    # Column 2: Direct Database Lookup for specific Drugs
    with col2:
        st.header("Drug Check")
        st.caption("Retrieve known side effects for a specific medication from the database")
        
        drug_query = st.text_input(
            "Enter drug name", 
            placeholder="e.g., Aspirin"
        )
        
        if st.button("Load Side Effects"):
            if drug_query:
                with st.spinner("Searching database..."):
                    try:
                        # Direct database query via backend
                        response = requests.get(
                            f"{BASE_URL}/drug-effects", 
                            params={"name": drug_query}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("side_effects"):
                                st.markdown("---")
                                st.markdown(f"#### Known Side Effects for: {drug_query}")
                                
                                # HTML/CSS badges for improved visual scannability of symptoms
                                badges = []
                                for se in data["side_effects"]:
                                    badges.append(
                                        f"<span style='background-color:#e1f5fe; color:#01579b; "
                                        f"padding:4px 10px; border-radius:15px; margin:4px; "
                                        f"display:inline-block; font-weight:bold; font-size:12px;'>{se}</span>"
                                    )
                                st.markdown("".join(badges), unsafe_allow_html=True)
                            else:
                                st.info("No side effects found for this drug name.")
                        else:
                            st.error(f"Backend error: {response.status_code}")
                            
                    except requests.exceptions.ConnectionError:
                        st.error("Connection Error: Is the FastAPI backend running?")
            else:
                st.warning("Please enter a drug name.")

# --- SECTION 2: REPORT SIDE EFFECT (User-generated Data) ---
elif choice == "Report Side Effect":
    st.header("Patient Reporting Portal")
    st.write("User-reported data helps identify undocumented side effects for further scientific review.")
    
    st.markdown("---")
    # Using a Streamlit form to manage state and submission logic
    with st.form("report_form", clear_on_submit=True):
        drug_input = st.text_input("Medication Name", placeholder="Enter the drug you took")
        symptom_input = st.text_area("Observations", placeholder="Describe the side effects you experienced")
        
        submitted = st.form_submit_button("Submit Official Report")
        
        if submitted:
            if drug_input and symptom_input:
                report_data = {"drug_name": drug_input, "symptom": symptom_input}
                try:
                    # POST request to persist the user report in the database logs
                    response = requests.post(f"{BASE_URL}/report-side-effect", json=report_data)
                    if response.status_code == 200:
                        st.success(response.json()["message"])
                    else:
                        error_detail = response.json().get('detail', 'Unknown error')
                        st.error(f"Submission failed: {error_detail}")
                except requests.exceptions.ConnectionError:
                    st.error("Connection failed: Unable to reach the backend server.")
            else:
                st.warning("Please fill out both the drug name and the symptom field.")

# --- SECTION 3: SCIENTIFIC ANALYSIS (Protein-Target Correlations) ---
elif choice == "Scientific Analysis":
    st.header("Scientific Protein-Target Analysis")
    st.write("Analysis of proteins that are common targets for drugs sharing identical side effects.")
    
    # Manual refresh button to clear cached results and fetch latest DB state
    if st.button("Refresh Scientific Data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    
    # Fetching correlation data from the cached function
    scientific_data = fetch_correlation_data()
    
    if scientific_data and isinstance(scientific_data, list):
        # Transforming JSON data into a pandas DataFrame for UI rendering
        df = pd.DataFrame(scientific_data)
        df.columns = ["Protein ID", "Side Effect", "Drug Count"]
        
        st.subheader("Correlation Data Overview")
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        
        # Subsection: Medication Drill Down for granular data inspection
        st.subheader("Medication Drill Down")
        st.write("Select a specific Protein and Side Effect to reveal the individual drugs involved:")
        
        # Creating a stable unique key for selection options
        df["Selection"] = df["Protein ID"].astype(str) + " | " + df["Side Effect"]
        selection_options = df["Selection"].tolist()
        
        # Using a key parameter to maintain widget state across Streamlit reruns
        selected_pair = st.selectbox(
            "Select pair to inspect:", 
            selection_options, 
            key="scientific_selection"
        )
        
        if selected_pair:
            # Parsing the selection string for API parameters
            p_id, s_effect = selected_pair.split(" | ")
            
            with st.spinner(f"Fetching specific medications for target {p_id}..."):
                try:
                    # Drill-down request to fetch individual drug names from the JOIN logic
                    drug_res = requests.get(
                        f"{BASE_URL}/science/target-drugs", 
                        params={"protein_id": p_id, "side_effect": s_effect}
                    )
                    
                    if drug_res.status_code == 200:
                        drugs = drug_res.json().get("drugs", [])
                        st.markdown(f"**Drugs targeting {p_id} that are linked to {s_effect}:**")
                        
                        if drugs:
                            for drug in drugs:
                                st.markdown(f"- {drug}")
                        else:
                            st.info("No individual drugs found for this specific target pair.")
                    else:
                        st.error(f"Backend error {drug_res.status_code}: {drug_res.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Backend unreachable. Please ensure the FastAPI server is running.")
    else:
        st.info("No scientific data available. Ensure the database and Materialized View are correctly initialized.")

# Sidebar footer for project metadata
st.sidebar.markdown("---")
st.sidebar.info("MediMatch AI - DBMS Project 2026")