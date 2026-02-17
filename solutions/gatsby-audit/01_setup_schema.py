import os
#!/usr/bin/env python3
"""
Step 1: Set up the pgvector schema for Gatsby RAG pipeline.
Run from bare metal — connects to postgres via kubernetes service.
"""

import psycopg2

# Connection config — adjust if using port-forward or NodePort
DB_CONFIG = {
    "host": "localhost",  # postgres ClusterIP
    "port": 5432,
    "dbname": "gatsby_rag",
    "user": os.getenv("DB_USER", "placeholder_user"),
    "password": os.getenv("DB_PASSWORD", "placeholder_pass")
}

SCHEMA = """
-- Gatsby text chunks with embeddings
CREATE TABLE IF NOT EXISTS gatsby_chunks (
    id SERIAL PRIMARY KEY,
    chapter INTEGER,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    embedding vector(1024),  -- BGE-Large produces 1024-dim vectors
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_gatsby_embedding 
    ON gatsby_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 20);

-- Essay section outline (versioned config)
CREATE TABLE IF NOT EXISTS essay_config (
    id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL,
    section_number INTEGER NOT NULL,
    section_title TEXT NOT NULL,
    metaphor TEXT NOT NULL,
    chapters TEXT NOT NULL,
    depth_strategy TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pipeline run audit log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    config_version INTEGER NOT NULL,
    step TEXT NOT NULL,
    section_number INTEGER,
    model_used TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

def main():
    print("Connecting to gatsby_rag database...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating schema...")
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            try:
                cur.execute(statement)
            except Exception as e:
                print(f"  Warning: {e}")

    # Insert the essay outline config (version 1)
    cur.execute("SELECT COUNT(*) FROM essay_config WHERE version = 1")
    if cur.fetchone()[0] == 0:
        print("Inserting essay outline v1...")
        sections = [
            (1, "Introduction: The Green Light", "The Green Light",
             "Ch. 1, 9", "Define as the 'unattainable future' and the death of the American Dream."),
            (2, "The Valley of Ashes", "The Valley of Ashes",
             "Ch. 1-2", "Focus on the moral and social decay resulting from uninhibited capitalism."),
            (3, "The Eyes of Doctor T.J. Eckleburg", "The Eyes of Doctor T.J. Eckleburg",
             "Ch. 2", "Analyze the eyes as a 'silent God' or the loss of spiritual values."),
            (4, "Gatsby's Library: The Uncut Books", "Gatsby's Library (Uncut Books)",
             "Ch. 3-4", "Discuss the 'theatricality' of wealth—it looks real but is unread/unlived."),
            (5, "The Defunct Mantelpiece Clock", "The Defunct Mantelpiece Clock",
             "Ch. 5", "Analyze Gatsby's attempt to 'stop time' during his reunion with Daisy."),
            (6, "Silver and Gold: Clothing and Colors", "Silver and Gold (Clothing/Colors)",
             "Ch. 6-7", "Focus on the performative nature of class and the 'masking' of origins."),
            (7, "The Hottest Day of the Year", "The Hottest Day of the Year",
             "Ch. 7", "Use the weather as a metaphor for the boiling point of the characters' tensions."),
            (8, "The Yellow Car: The Death Car", "The Yellow Car (Death Car)",
             "Ch. 8", "Analyze the car as a symbol of reckless consumerism and destruction."),
            (9, "The Holocaust of Gatsby's Death", "The Holocaust of Gatsby's Death",
             "Ch. 8", "Discuss the accidental nature of the tragedy and the indifference of the rich."),
            (10, "The Fresh, Green Breast of the New World", "The Fresh, Green Breast of the New World",
             "Ch. 9", "Connect the ending back to the original Dutch sailors and the 'lost' dream."),
            (11, "Synthesis: Boats Against the Current", "The Boats Against the Current",
             "Ch. 9", "Final analysis of the human struggle against time and nostalgia."),
        ]
        for sec in sections:
            cur.execute(
                "INSERT INTO essay_config (version, section_number, section_title, metaphor, chapters, depth_strategy) "
                "VALUES (1, %s, %s, %s, %s, %s)",
                sec
            )
        print(f"  Inserted {len(sections)} sections.")

    # Verify
    cur.execute("SELECT COUNT(*) FROM essay_config WHERE version = 1")
    print(f"Essay config v1: {cur.fetchone()[0]} sections")
    cur.execute("SELECT COUNT(*) FROM gatsby_chunks")
    print(f"Gatsby chunks: {cur.fetchone()[0]} (will populate in step 2)")

    cur.close()
    conn.close()
    print("Schema setup complete.")


if __name__ == "__main__":
    main()
