#!/usr/bin/env python3
"""
Step 3: LangGraph Essay Generation Pipeline
- Reads essay outline from pgvector (versioned config)
- Per-section: RAG retrieval -> DeepSeek 70B generation
- Logs every step to Delta Lake (MinIO)
- Assembles final 10-page essay
"""

import os
import json
import uuid
import time
from datetime import datetime
from typing import TypedDict, List, Optional

import pandas as pd
import psycopg2
import httpx
from deltalake import write_deltalake, DeltaTable
from sentence_transformers import SentenceTransformer
from langgraph.graph import StateGraph, END

# =============================================================================
# Configuration
# =============================================================================

DB_CONFIG = {
    "host": "localhost",  # via kubectl port-forward svc/postgres 5432:5432
    "port": 5432,
    "dbname": "gatsby_rag",
    "user": os.getenv("DB_USER", "placeholder_user"),
    "password": os.getenv("DB_PASSWORD", "placeholder_pass")
}

DEEPSEEK_URL = "http://10.10.10.2:8080/v1/chat/completions"
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
TOP_K = 8  # number of passages to retrieve per section

MINIO_STORAGE = {
    "endpoint_url": os.getenv("MINIO_ENDPOINT", "http://10.10.10.2:30900"),
    "access_key_id": os.getenv("MINIO_ACCESS_KEY", "PLACEHOLDER_ADMIN"),
    "secret_access_key": os.getenv("MINIO_SECRET_KEY", "PLACEHOLDER_ADMIN"),
    "region": "us-east-1",
    "allow_http": "true"
}

DELTA_BASE = "s3://sovereign-lakehouse/gatsby-pipeline"
RUN_ID = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

# =============================================================================
# State Definition
# =============================================================================

class PipelineState(TypedDict):
    run_id: str
    config_version: int
    sections: List[dict]
    current_section_idx: int
    drafts: List[dict]  # {section_number, title, content}
    full_essay: str
    status: str
    error: Optional[str]

# =============================================================================
# Helpers
# =============================================================================

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def log_to_delta(table_path, data_dict):
    """Append a record to a Delta Lake table."""
    df = pd.DataFrame([data_dict])
    try:
        write_deltalake(
            f"{DELTA_BASE}/{table_path}",
            df,
            storage_options=MINIO_STORAGE,
            mode="append"
        )
    except Exception as e:
        print(f"  [WARN] Delta Lake write failed: {e}")

def retrieve_passages(query: str, chapter_filter: str, top_k: int = TOP_K):
    """RAG retrieval from pgvector."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Generate query embedding
    embedding = embedder.encode(
        f"Represent this query for retrieval: {query}",
        normalize_embeddings=True
    ).tolist()

    # Parse chapter filter like "Ch. 1-2" or "Ch. 5" or "Ch. 6-7"
    chapters = []
    ch_str = chapter_filter.replace("Ch.", "").replace("ch.", "").strip()
    for part in ch_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            chapters.extend(range(int(start.strip()), int(end.strip()) + 1))
        else:
            chapters.append(int(part))

    if chapters:
        placeholders = ",".join(["%s"] * len(chapters))
        cur.execute(f"""
            SELECT chapter, chunk_index, text,
                   1 - (embedding <=> %s::vector) as similarity
            FROM gatsby_chunks
            WHERE chapter IN ({placeholders})
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [str(embedding)] + chapters + [str(embedding), top_k])
    else:
        cur.execute("""
            SELECT chapter, chunk_index, text,
                   1 - (embedding <=> %s::vector) as similarity
            FROM gatsby_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (str(embedding), str(embedding), top_k))

    results = cur.fetchall()
    cur.close()
    conn.close()

    return [{"chapter": r[0], "chunk": r[1], "text": r[2], "similarity": r[3]} for r in results]


def call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 2048):
    """Call DeepSeek 70B via llama.cpp OpenAI-compatible API."""
    import re
    with httpx.Client(timeout=600.0) as client:
        response = client.post(
            DEEPSEEK_URL,
            json={
                "model": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "top_p": 0.9
            }
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Strip DeepSeek R1 thinking tags
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        return content

# =============================================================================
# LangGraph Nodes
# =============================================================================

def load_config(state: PipelineState) -> dict:
    """Load essay outline from pgvector."""
    print(f"\n{'='*60}")
    print(f"Pipeline Run: {state['run_id']}")
    print(f"{'='*60}")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT section_number, section_title, metaphor, chapters, depth_strategy
        FROM essay_config
        WHERE version = %s
        ORDER BY section_number
    """, (state["config_version"],))

    sections = []
    for row in cur.fetchall():
        sections.append({
            "section_number": row[0],
            "title": row[1],
            "metaphor": row[2],
            "chapters": row[3],
            "depth_strategy": row[4]
        })

    cur.close()
    conn.close()

    print(f"Loaded {len(sections)} sections from config v{state['config_version']}")

    log_to_delta("audit/pipeline_runs", {
        "run_id": state["run_id"],
        "step": "load_config",
        "config_version": state["config_version"],
        "sections_loaded": len(sections),
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    })

    return {"sections": sections, "current_section_idx": 0, "drafts": []}


def generate_section(state: PipelineState) -> dict:
    """Generate one essay section using RAG + DeepSeek."""
    idx = state["current_section_idx"]
    section = state["sections"][idx]

    print(f"\n--- Section {section['section_number']}: {section['title']} ---")

    # 1. RAG retrieval
    query = f"{section['metaphor']} {section['depth_strategy']}"
    print(f"  Retrieving passages for: {query[:80]}...")
    passages = retrieve_passages(query, section["chapters"])
    print(f"  Retrieved {len(passages)} passages (best sim: {passages[0]['similarity']:.4f})")

    # 2. Build prompt with retrieved context
    context_block = "\n\n".join([
        f"[Chapter {p['chapter']}, Passage {p['chunk']}]:\n{p['text']}"
        for p in passages
    ])

    # Determine thematic link based on section
    theme_map = {
        1: "The Disintegration of the American Dream",
        2: "The Moral Consequences of Uninhibited Capitalism",
        3: "The Absence of Spiritual and Moral Authority",
        4: "The Performative Nature of Wealth and Identity",
        5: "The Futility of Recapturing the Past",
        6: "Class Performance and the Masking of Origins",
        7: "The Eruption of Concealed Tensions",
        8: "Reckless Consumerism and Its Human Cost",
        9: "The Indifference of the Privileged Class",
        10: "The Corruption of the Original American Promise",
        11: "The Inescapable Pull of the Past"
    }
    theme = theme_map.get(section["section_number"], "The Disintegration of the American Dream")

    system_prompt = (
        "You are a Senior AI Solutions Architect and Literary Analyst. Your goal is to produce "
        "a high-fidelity analytical section for a 10-page master's level thesis on 'The Great Gatsby' (1925). "
        "You must use the provided RAG context to cite the text exactly. Your tone should be scholarly, "
        "precise, and sophisticated—suitable for a GS-15 level federal policy advisor. "
        "Do NOT include any meta-commentary, preamble, or notes about your thinking process in the output. "
        "Output ONLY the polished analytical section."
    )

    user_prompt = f"""Context:
{context_block}

Task: Analyze the metaphor of "{section['metaphor']}" within the 1925 text of 'The Great Gatsby'.

Requirements:
1. Length: Write exactly 450–550 words for this section.
2. Citations: You must include at least two direct quotes from the provided context. Follow each quote with a chapter citation (e.g., Chapter III).
3. Thematic Link: Connect this specific metaphor to the broader theme of {theme}.
4. Linguistic Precision: Avoid filler words. Use advanced vocabulary (e.g., 'meretricious', 'ephemeral', 'stagnation').
5. Reasoning: Before writing, use your internal thinking process to determine how this metaphor foreshadows the novel's conclusion.

Output Format:
Section {section['section_number']}: {section['title']}
[Your Analysis Here]"""

    # 3. Generate with DeepSeek
    print(f"  Generating analysis...")
    start_time = time.time()
    content = call_deepseek(system_prompt, user_prompt, max_tokens=4096)
    gen_time = time.time() - start_time
    print(f"  Generated {len(content.split())} words in {gen_time:.1f}s")

    # 4. Log to Delta Lake
    draft_record = {
        "run_id": state["run_id"],
        "section_number": section["section_number"],
        "section_title": section["title"],
        "metaphor": section["metaphor"],
        "chapters_referenced": section["chapters"],
        "passages_retrieved": len(passages),
        "best_similarity": passages[0]["similarity"],
        "content": content,
        "word_count": len(content.split()),
        "generation_time_seconds": round(gen_time, 2),
        "model": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
        "timestamp": datetime.now().isoformat()
    }

    log_to_delta("drafts/sections", draft_record)

    log_to_delta("audit/pipeline_runs", {
        "run_id": state["run_id"],
        "step": f"generate_section_{section['section_number']}",
        "config_version": state["config_version"],
        "sections_loaded": 0,
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    })

    # 5. Update state
    new_drafts = state["drafts"] + [{
        "section_number": section["section_number"],
        "title": section["title"],
        "content": content
    }]

    return {
        "drafts": new_drafts,
        "current_section_idx": idx + 1
    }


def should_continue(state: PipelineState) -> str:
    """Route: more sections or assemble?"""
    if state["current_section_idx"] < len(state["sections"]):
        return "generate"
    return "assemble"


def assemble_essay(state: PipelineState) -> dict:
    """Stitch all sections into the final essay."""
    print(f"\n{'='*60}")
    print("Assembling final essay...")
    print(f"{'='*60}")

    essay_parts = []
    essay_parts.append("# Metaphors in The Great Gatsby: A Literary Analysis\n")
    essay_parts.append("## F. Scott Fitzgerald's Vision of the American Dream\n")

    for draft in sorted(state["drafts"], key=lambda d: d["section_number"]):
        essay_parts.append(f"\n## {draft['title']}\n")
        essay_parts.append(draft["content"])
        essay_parts.append("")

    full_essay = "\n".join(essay_parts)
    word_count = len(full_essay.split())
    page_estimate = word_count / 500  # ~500 words per page

    print(f"Total words: {word_count}")
    print(f"Estimated pages: {page_estimate:.1f}")

    # Log final essay to Delta Lake
    log_to_delta("drafts/final_essay", {
        "run_id": state["run_id"],
        "config_version": state["config_version"],
        "full_essay": full_essay,
        "word_count": word_count,
        "page_estimate": round(page_estimate, 1),
        "sections_count": len(state["drafts"]),
        "model": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
        "timestamp": datetime.now().isoformat()
    })

    # Also save locally
    output_path = f"./essay_{state['run_id']}.md"
    with open(output_path, "w") as f:
        f.write(full_essay)
    print(f"Saved to: {output_path}")

    return {
        "full_essay": full_essay,
        "status": f"Complete: {word_count} words, ~{page_estimate:.1f} pages"
    }

# =============================================================================
# Build the Graph
# =============================================================================

def build_pipeline():
    builder = StateGraph(PipelineState)

    builder.add_node("load_config", load_config)
    builder.add_node("generate_section", generate_section)
    builder.add_node("assemble_essay", assemble_essay)

    builder.set_entry_point("load_config")
    builder.add_edge("load_config", "generate_section")
    builder.add_conditional_edges(
        "generate_section",
        should_continue,
        {
            "generate": "generate_section",
            "assemble": "assemble_essay"
        }
    )
    builder.add_edge("assemble_essay", END)

    return builder.compile()

# =============================================================================
# Main
# =============================================================================

# Load embedding model globally (CPU — GPUs reserved for DeepSeek)
print("Loading embedding model...")
embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

if __name__ == "__main__":
    pipeline = build_pipeline()

    print(f"\nStarting Gatsby Analysis Pipeline")
    print(f"Run ID: {RUN_ID}")

    result = pipeline.invoke({
        "run_id": RUN_ID,
        "config_version": 1,
        "sections": [],
        "current_section_idx": 0,
        "drafts": [],
        "full_essay": "",
        "status": "starting",
        "error": None
    })

    print(f"\n{'='*60}")
    print(f"Pipeline Complete: {result['status']}")
    print(f"{'='*60}")
