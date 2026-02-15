import pandas as pd
import requests
import tarfile
import io

def inspect_remote_archive(url):
    """
    Fetches a remote compressed archive (.tar.gz), extracts the primary data file, 
    and inspects its schema and content without saving the file locally.
    
    This utility is used during the development phase to ensure the database 
    schema aligns with the actual source data provided by external databases 
    like SNAP or SIDER.
    """
    print(f"Initiating connection to: {url}")
    
    try:
        # Stream the response to handle large files efficiently
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Load the content into an in-memory byte stream
        file_content = io.BytesIO(response.content)
        
        # Open the tarball archive in 'read:gz' mode
        with tarfile.open(fileobj=file_content, mode="r:gz") as tar:
            # List all file members contained within the compressed archive
            members = tar.getnames()
            print(f"Archive structure identified: {members}")
            
            # Access the first member of the archive for schema inspection
            if not members:
                print("Error: The archive is empty.")
                return
                
            first_file = tar.extractfile(members[0])
            
            # Load only a subset of data (first 5 rows) to optimize memory 
            # and processing speed during the inspection phase.
            # 'latin1' encoding is used to handle potential non-UTF8 characters 
            # common in medical datasets.
            df = pd.read_csv(first_file, sep=',', nrows=5, encoding='latin1')
            
            # Output the column names to verify against the SQL import logic
            print("\n--- SCHEMA VALIDATION: COLUMN NAMES ---")
            print(df.columns.tolist())
            
            # Output a preview of the actual data to verify delimiters and encoding
            print("\n--- DATA PREVIEW: FIRST 5 ROWS ---")
            print(df.head())

    except requests.exceptions.RequestException as e:
        print(f"Network error: Failed to fetch the file. {e}")
    except tarfile.TarError as e:
        print(f"Extraction error: Failed to process the compressed archive. {e}")
    except Exception as e:
        print(f"Unexpected error during file inspection: {e}")

# Main execution block for independent testing of the SNAP dataset
if __name__ == "__main__":
    # URL target: Bio-Decagon targets from the SNAP database
    TARGET_URL = "http://snap.stanford.edu/decagon/bio-decagon-targets.tar.gz"
    inspect_remote_archive(TARGET_URL)