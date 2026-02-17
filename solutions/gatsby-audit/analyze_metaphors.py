import duckdb
import os

# --- Sovereign Lab Configuration ---
# Use port 30900 for API (S3) traffic
MINIO_ENDPOINT = "10.10.10.2:30900" 
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio_user")   
MINIO_SECRET_KEY = "PLACEHOLDER_KEY"   
BUCKET_NAME = "ai-research"
TABLE_PATH = f"s3://{sovereign-lakehouse}/metaphors_delta"

# Persistent DB file in your labs folder
DB_FILE = os.path.expanduser("~/labs/sovereign-ai/sovereign_analytics.duckdb")

def run_analytics():
    # 1. Connect to DuckDB
    con = duckdb.connect(DB_FILE)

    # 2. Install/Load extensions (DuckDB handles this automatically if already installed)
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL delta; LOAD delta;")

    # 3. Authenticate to your Local MinIO
    con.execute(f"""
        CREATE OR REPLACE SECRET minio_secret (
            TYPE S3,
            KEY_ID '{os.getenv('MINIO_ACCESS_KEY', 'user')}',
            SECRET 'os.getenv("MINIO_SECRET_KEY", "placeholder")',
            ENDPOINT '{MINIO_ENDPOINT}',
            URL_STYLE 'path',
            USE_SSL false
        );
    """)

    print(f"🔍 Querying MinIO Lakehouse: {TABLE_PATH}...")

    try:
        # 4. Run the Analysis
        # This counts metaphors by type (e.g., Technical, Literary, Cultural)
        query = f"""
            SELECT 
                metaphor_type, 
                COUNT(*) as total_found
            FROM delta_scan('{TABLE_PATH}')
            GROUP BY 1
            ORDER BY total_found DESC;
        """
        
        results = con.execute(query).df()
        
        if results.empty:
            print("sadly, the table is empty. did the 70B model finish its run?")
        else:
            print("\n--- Metaphor Analysis Results ---")
            print(results)
            
    except Exception as e:
        print(f"❌ Error: Could not read Delta table. {e}")
    finally:
        con.close()

if __name__ == "__main__":
    run_analytics()
