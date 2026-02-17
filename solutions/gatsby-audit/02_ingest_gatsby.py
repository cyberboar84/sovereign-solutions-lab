import os
#!/usr/bin/env python3
"""
Step 2: Ingest The Great Gatsby into pgvector.
- Splits by chapter, then into paragraph-level chunks with overlap
- Generates BGE-Large embeddings
- Stores in postgres with pgvector
"""

import re
import psycopg2
from sentence_transformers import SentenceTransformer

# Config
GATSBY_PATH = "./gatsby.txt"
CHUNK_SIZE = 500       # target tokens per chunk (~words as approximation)
CHUNK_OVERLAP = 150    # overlap tokens between chunks
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"  # 1024-dim

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gatsby_rag",
    "user": os.getenv("DB_USER", "placeholder_user"),
    "password": os.getenv("DB_PASSWORD", "placeholder_pass")
}


def load_and_split_chapters(filepath):
    """Load Gatsby text and split into chapters."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Strip Gutenberg header/footer
    start_markers = ["CHAPTER I", "Chapter I", "Chapter 1"]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "***END OF THE PROJECT GUTENBERG",
        "End of the Project Gutenberg"
    ]

    start_idx = 0
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            start_idx = idx
            break

    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            end_idx = idx
            break

    text = text[start_idx:end_idx].strip()

    # Split into chapters
    chapter_pattern = r'(?=Chapter\s+[IVXLCDM]+\b|CHAPTER\s+[IVXLCDM]+\b)'
    chapters = re.split(chapter_pattern, text, flags=re.IGNORECASE)
    chapters = [c.strip() for c in chapters if c.strip()]

    print(f"Found {len(chapters)} chapters")
    return chapters


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks at paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_words = len(para.split())

        if current_size + para_words > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Calculate overlap — keep last paragraphs up to overlap size
            overlap_size = 0
            overlap_paras = []
            for p in reversed(current_chunk):
                p_size = len(p.split())
                if overlap_size + p_size <= overlap:
                    overlap_paras.insert(0, p)
                    overlap_size += p_size
                else:
                    break

            current_chunk = overlap_paras
            current_size = overlap_size

        current_chunk.append(para)
        current_size += para_words

    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def main():
    print("Loading BGE-Large embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Model loaded. Embedding dim: {model.get_sentence_embedding_dimension()}")

    print(f"\nLoading Gatsby from {GATSBY_PATH}...")
    chapters = load_and_split_chapters(GATSBY_PATH)

    print("\nConnecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Clear existing chunks for re-ingestion
    cur.execute("DELETE FROM gatsby_chunks")
    print("Cleared existing chunks.")

    total_chunks = 0
    for ch_idx, chapter_text in enumerate(chapters):
        ch_num = ch_idx + 1
        chunks = chunk_text(chapter_text)
        print(f"\n  Chapter {ch_num}: {len(chunks)} chunks")

        for chunk_idx, chunk in enumerate(chunks):
            # Generate embedding with BGE instruction prefix for retrieval
            embedding = model.encode(
                f"Represent this passage for retrieval: {chunk}",
                normalize_embeddings=True
            ).tolist()

            cur.execute(
                "INSERT INTO gatsby_chunks (chapter, chunk_index, text, embedding) "
                "VALUES (%s, %s, %s, %s)",
                (ch_num, chunk_idx, chunk, str(embedding))
            )
            total_chunks += 1

    # Recreate the IVFFlat index now that we have data
    print(f"\nTotal chunks inserted: {total_chunks}")
    print("Rebuilding vector index...")
    cur.execute("DROP INDEX IF EXISTS idx_gatsby_embedding")

    # IVFFlat lists should be sqrt(n) roughly
    import math
    n_lists = max(1, int(math.sqrt(total_chunks)))
    cur.execute(f"""
        CREATE INDEX idx_gatsby_embedding 
        ON gatsby_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {n_lists})
    """)

    # Verify
    cur.execute("SELECT COUNT(*) FROM gatsby_chunks")
    print(f"Verified: {cur.fetchone()[0]} chunks in database")

    # Sample similarity search test
    test_query = "the green light at the end of Daisy's dock"
    test_embedding = model.encode(
        f"Represent this query for retrieval: {test_query}",
        normalize_embeddings=True
    ).tolist()

    cur.execute("""
        SELECT chapter, chunk_index, text, 
               1 - (embedding <=> %s::vector) as similarity
        FROM gatsby_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT 3
    """, (str(test_embedding), str(test_embedding)))

    print(f"\nTest query: '{test_query}'")
    print("Top 3 results:")
    for row in cur.fetchall():
        print(f"  Ch.{row[0]} chunk {row[1]} (sim: {row[3]:.4f})")
        print(f"    {row[2][:150]}...")

    cur.close()
    conn.close()
    print("\nIngestion complete.")


if __name__ == "__main__":
    main()
