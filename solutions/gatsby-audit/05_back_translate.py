import os
#!/usr/bin/env python3
"""
Step 5: Back-Translation Audit Pipeline
- Reads Spanish and Mandarin translations
- Back-translates to English via Mistral-Nemo (Triton)
- Compares back-translations against original English
- Computes similarity scores using BGE-Large embeddings
- Logs everything to Delta Lake
- Saves back-translated .md files for review
"""

import os
import json
import time
import uuid
from datetime import datetime

import httpx
import numpy as np
import pandas as pd
from deltalake import write_deltalake
from sentence_transformers import SentenceTransformer

# =============================================================================
# Configuration
# =============================================================================

# Mistral-Nemo via triton-adapter (through LiteLLM or direct)
MISTRAL_URL = "http://10.10.10.2:30400/v1/chat/completions"  # LiteLLM NodePort
MISTRAL_API_KEY = os.getenv("SOVEREIGN_API_KEY", "your-key-here")
MISTRAL_MODEL = "Mistral-Nemo-Sovereign"

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
RUN_ID = f"backtranslate-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

PIPELINE_DIR = "."

MINIO_STORAGE = {
    "endpoint_url": "http://10.10.10.2:30900",
    "access_key_id": os.getenv("MINIO_ACCESS_KEY", "minio_user"),
    "secret_access_key": os.getenv("SOV_SECRET_KEY", "placeholder_key"),
    "region": "us-east-1",
    "allow_http": "true"
}

DELTA_BASE = "s3://sovereign-lakehouse/gatsby-pipeline"

# Files to back-translate
TRANSLATIONS = [
    {
        "language": "Spanish",
        "code": "es",
        "essay_path": os.path.join(PIPELINE_DIR, "essay_es.md"),
        "summary_path": os.path.join(PIPELINE_DIR, "summary_es.md"),
    },
    {
        "language": "Mandarin",
        "code": "zh",
        "essay_path": os.path.join(PIPELINE_DIR, "essay_zh.md"),
        "summary_path": os.path.join(PIPELINE_DIR, "summary_zh.md"),
    }
]

# Original English files for comparison
ORIGINAL_ESSAY = os.path.join(PIPELINE_DIR, "essay_run-20260213-171412-1a3870.md")
ORIGINAL_SUMMARY = os.path.join(PIPELINE_DIR, "executive_summary.md")

# =============================================================================
# Helpers
# =============================================================================

def log_to_delta(table_path, data_dict):
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


def back_translate(text, source_language, max_chunk_words=600):
    """
    Back-translate text to English via Mistral-Nemo.
    Splits by sections for long texts.
    """
    instruction = (
        f"You are a professional translator. Translate the following {source_language} text "
        f"back into English. Preserve the academic tone, formatting, and all citations. "
        f"Output ONLY the English translation, nothing else."
    )

    # Split by section headers or double newlines
    sections = []
    current_section = []
    for line in text.split("\n"):
        # Match headers in any language (## or #)
        if (line.startswith("## ") or line.startswith("# ")) and current_section:
            sections.append("\n".join(current_section))
            current_section = [line]
        else:
            current_section.append(line)
    if current_section:
        sections.append("\n".join(current_section))

    # If we only got 1 section (headers were translated), split by double newlines
    if len(sections) <= 1:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        sections = []
        current_chunk = []
        current_words = 0
        for para in paragraphs:
            para_words = len(para.split())
            if current_words + para_words > max_chunk_words and current_chunk:
                sections.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_words = para_words
            else:
                current_chunk.append(para)
                current_words += para_words
        if current_chunk:
            sections.append("\n\n".join(current_chunk))

    # Short text — translate in one shot
    if len(text.split()) < max_chunk_words:
        sections = [text]

    translated_sections = []
    total_time = 0

    for i, section in enumerate(sections):
        if not section.strip():
            translated_sections.append("")
            continue

        print(f"    Section {i+1}/{len(sections)} ({len(section.split())} words)...")

        start = time.time()
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                MISTRAL_URL,
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": section}
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.2
                }
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]

        elapsed = time.time() - start
        total_time += elapsed
        print(f"      -> {len(result.split())} words, {elapsed:.1f}s")
        translated_sections.append(result)

    return "\n\n".join(translated_sections), total_time


def compute_similarity(text_a, text_b, embedder):
    """Compute cosine similarity between two texts using BGE-Large."""
    emb_a = embedder.encode(f"Represent this text: {text_a[:2000]}", normalize_embeddings=True)
    emb_b = embedder.encode(f"Represent this text: {text_b[:2000]}", normalize_embeddings=True)
    similarity = float(np.dot(emb_a, emb_b))
    return similarity


def section_comparison(original, back_translated, embedder):
    """Compare original and back-translated section by section."""
    # Split both into sections
    def split_sections(text):
        sections = []
        current = []
        for line in text.split("\n"):
            if line.startswith("## ") and current:
                sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current))
        return [s for s in sections if s.strip()]

    orig_sections = split_sections(original)
    bt_sections = split_sections(back_translated)

    # Compare pairwise (handle length mismatches)
    n = min(len(orig_sections), len(bt_sections))
    scores = []
    for i in range(n):
        sim = compute_similarity(orig_sections[i], bt_sections[i], embedder)
        scores.append(sim)

    return scores


# =============================================================================
# Main Pipeline
# =============================================================================

def main():
    print(f"{'='*60}")
    print(f"Back-Translation Audit Pipeline")
    print(f"Run ID: {RUN_ID}")
    print(f"{'='*60}")

    # Load originals
    with open(ORIGINAL_ESSAY, "r") as f:
        original_essay = f.read()
    with open(ORIGINAL_SUMMARY, "r") as f:
        original_summary = f.read()

    # Load embedder for similarity
    print("\nLoading embedding model...")
    embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

    results = []

    for trans in TRANSLATIONS:
        lang = trans["language"]
        code = trans["code"]

        print(f"\n{'='*60}")
        print(f"Back-translating {lang}")
        print(f"{'='*60}")

        for doc_type, trans_path, original_text in [
            ("essay", trans["essay_path"], original_essay),
            ("summary", trans["summary_path"], original_summary)
        ]:
            print(f"\n  [{lang}] Back-translating {doc_type}...")

            with open(trans_path, "r", encoding="utf-8") as f:
                translated_text = f.read()

            # Back-translate
            back_translation, gen_time = back_translate(translated_text, lang)

            # Save back-translated file
            bt_filename = f"{doc_type}_bt_{code}.md"
            bt_path = os.path.join(PIPELINE_DIR, bt_filename)
            with open(bt_path, "w", encoding="utf-8") as f:
                f.write(back_translation)
            print(f"  Saved: {bt_path}")

            # Compute overall similarity
            overall_sim = compute_similarity(original_text, back_translation, embedder)
            print(f"  Overall semantic similarity: {overall_sim:.4f}")

            # Section-level comparison for essays
            section_scores = []
            if doc_type == "essay":
                section_scores = section_comparison(original_text, back_translation, embedder)
                print(f"  Section similarities: {[f'{s:.3f}' for s in section_scores]}")
                avg_section = sum(section_scores) / len(section_scores) if section_scores else 0
                print(f"  Average section similarity: {avg_section:.4f}")

            # Log to Delta Lake
            log_to_delta(f"back_translations/{code}", {
                "run_id": RUN_ID,
                "document": doc_type,
                "source_language": lang,
                "language_code": code,
                "back_translated_word_count": len(back_translation.split()),
                "original_word_count": len(original_text.split()),
                "overall_similarity": round(overall_sim, 4),
                "section_similarities": json.dumps(section_scores),
                "avg_section_similarity": round(sum(section_scores) / len(section_scores), 4) if section_scores else None,
                "content": back_translation,
                "generation_time_seconds": round(gen_time, 2),
                "model": "Mistral-Nemo-12B",
                "timestamp": datetime.now().isoformat()
            })

            log_to_delta("audit/pipeline_runs", {
                "run_id": RUN_ID,
                "step": f"back_translate_{doc_type}_{code}",
                "config_version": 1,
                "sections_loaded": 0,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })

            results.append({
                "language": lang,
                "document": doc_type,
                "similarity": overall_sim,
                "filename": bt_filename
            })

    # Final Report
    print(f"\n{'='*60}")
    print("Back-Translation Audit Report")
    print(f"{'='*60}")
    print(f"\n{'Language':<12} {'Document':<10} {'Similarity':<12} {'File'}")
    print("-" * 55)
    for r in results:
        status = "PASS" if r["similarity"] > 0.85 else "REVIEW" if r["similarity"] > 0.75 else "FAIL"
        print(f"{r['language']:<12} {r['document']:<10} {r['similarity']:.4f} [{status}]  {r['filename']}")

    print(f"\nThreshold: >0.85 PASS | 0.75-0.85 REVIEW | <0.75 FAIL")
    print(f"\nAll back-translations saved to: {PIPELINE_DIR}")


if __name__ == "__main__":
    main()
