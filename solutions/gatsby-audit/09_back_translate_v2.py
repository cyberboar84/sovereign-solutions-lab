import os
#!/usr/bin/env python3
"""
Step 09: Back-Translation Audit Pipeline v2
- Back-translates Spanish and Mandarin to English via Llama-3.3-70B
- Literal translation to expose semantic drift
- Compares against originals using BGE-Large embeddings
- Logs to Delta Lake
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

LLAMA_URL = "http://localhost:8080/v1/chat/completions"
Key = os.getenv("SOVEREIGN_API_KEY", "your-key-here")
MISTRAL_MODEL = "llama-3.3"

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
RUN_ID = f"backtranslate-v2-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

PIPELINE_DIR = "."

MINIO_STORAGE = {
    "endpoint_url": "http://10.10.10.2:30900",
    "access_key_id": os.getenv("MINIO_ACCESS_KEY", "minio_user"),
    "secret_access_key": os.getenv("MINIO_SECRET_KEY", "PLACEHOLDER_KEY"),
    "region": "us-east-1",
    "allow_http": "true"
}

DELTA_BASE = "s3://sovereign-lakehouse/gatsby-pipeline"

ORIGINAL_ESSAY = os.path.join(PIPELINE_DIR, "essay_run-20260214-150657-bcf43f.md")
ORIGINAL_SUMMARY = os.path.join(PIPELINE_DIR, "executive_summary_v3.md")

BACK_TRANSLATE_SYSTEM = {
    "Spanish": (
        "You are a Philological Auditor performing a translation quality control audit. "
        "Your task is to translate Spanish text back into English as literally as possible "
        "to detect semantic drift from the original 1925 source material.\n\n"
        "STRICT RULES:\n"
        "1. Translate as literally as possible. Preserve the exact structure and word order where feasible.\n"
        "2. Do NOT correct or improve the translation. If something sounds awkward, stilted, or wrong "
        "in English, KEEP IT — this reveals where meaning was lost or altered.\n"
        "3. Do NOT correct for flow or regional naturalism. Only flag errors where the semantic meaning "
        "of the original 1920s metaphor has been lost or mistranslated into a local idiom.\n"
        "4. If a metaphor was translated to a different concept (e.g., 'boats against the current' became "
        "'ships fighting the tide'), translate that different concept literally — do NOT substitute "
        "the original English metaphor.\n"
        "5. Keep all citations and Markdown formatting exactly as they appear.\n"
        "6. Do NOT add any translator's notes, explanations, or commentary.\n"
        "7. Do NOT use the word 'Note:' or add any meta-text."
    ),
    "Mandarin": (
        "You are a Philological Auditor performing a translation quality control audit. "
        "Your task is to translate Mandarin Chinese text back into English as literally as possible "
        "to detect semantic drift from the original 1925 source material.\n\n"
        "STRICT RULES:\n"
        "1. Translate as literally as possible. If the Chinese used a Chengyu or idiom, translate the "
        "idiom literally — do NOT replace it with the original English phrasing.\n"
        "2. Do NOT correct or improve the translation. If something sounds awkward, stilted, or wrong "
        "in English, KEEP IT — this reveals where meaning was lost or altered.\n"
        "3. Do NOT correct for flow or regional naturalism. Only flag errors where the semantic meaning "
        "of the original 1920s metaphor has been lost or mistranslated.\n"
        "4. If a metaphor was translated to a different concept, translate that different concept "
        "literally — do NOT substitute the original English metaphor.\n"
        "5. Keep all citations and Markdown formatting exactly as they appear.\n"
        "6. Do NOT add any translator's notes, explanations, or commentary.\n"
        "7. Do NOT use the word 'Note:' or add any meta-text."
    )
}

TRANSLATIONS = [
    {
        "language": "Spanish",
        "code": "es",
        "essay_path": os.path.join(PIPELINE_DIR, "essay_es_v2.md"),
        "summary_path": os.path.join(PIPELINE_DIR, "summary_es_v2.md"),
    },
    {
        "language": "Mandarin",
        "code": "zh",
        "essay_path": os.path.join(PIPELINE_DIR, "essay_zh_v2.md"),
        "summary_path": os.path.join(PIPELINE_DIR, "summary_zh_v2.md"),
    }
]

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


def split_into_sections(text, max_chunk_words=500):
    """Split by ## headers or fall back to paragraph chunking."""
    sections = []
    current_section = []

    for line in text.split("\n"):
        if (line.startswith("## ") or line.startswith("# ")) and current_section:
            sections.append("\n".join(current_section))
            current_section = [line]
        else:
            current_section.append(line)
    if current_section:
        sections.append("\n".join(current_section))

    # Fallback: chunk by paragraphs
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

    return sections


def back_translate(text, source_language, system_prompt):
    """Back-translate text to English via Llama-3.3-70B, section by section."""
    user_prefix = (
        f"Translate this {source_language} text back into English. "
        f"This is a quality control audit — translate as literally as possible.\n\n"
        f"Source Text:\n"
    )

    # Always try header splitting first (Chinese has few space-separated words but many characters)
    sections = split_into_sections(text)
    if len(sections) <= 1 and len(text.split()) < 500 and len(text) < 3000:
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
                LLAMA_URL,
                headers={"Authorization": f"Bearer {"no-key"}"},
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"{user_prefix}{section}"}
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
    """Cosine similarity between two texts using BGE-Large."""
    emb_a = embedder.encode(f"Represent this text: {text_a[:2000]}", normalize_embeddings=True)
    emb_b = embedder.encode(f"Represent this text: {text_b[:2000]}", normalize_embeddings=True)
    return float(np.dot(emb_a, emb_b))


def section_comparison(original, back_translated, embedder):
    """Compare section-by-section similarity."""
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
        return [s for s in sections if s.strip() and len(s.split()) > 20]

    orig_sections = split_sections(original)
    bt_sections = split_sections(back_translated)

    n = min(len(orig_sections), len(bt_sections))
    scores = []
    for i in range(n):
        sim = compute_similarity(orig_sections[i], bt_sections[i], embedder)
        scores.append(round(sim, 4))

    return scores


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"{'='*60}")
    print(f"Back-Translation Audit Pipeline v2")
    print(f"Run ID: {RUN_ID}")
    print(f"{'='*60}")

    # Load originals
    with open(ORIGINAL_ESSAY, "r") as f:
        original_essay = f.read()

    original_summary = ""
    if os.path.exists(ORIGINAL_SUMMARY):
        with open(ORIGINAL_SUMMARY, "r") as f:
            original_summary = f.read()

    # Load embedder
    print("\nLoading embedding model...")
    embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

    results = []

    for trans in TRANSLATIONS:
        lang = trans["language"]
        code = trans["code"]
        system_prompt = BACK_TRANSLATE_SYSTEM[lang]

        print(f"\n{'='*60}")
        print(f"Back-translating {lang}")
        print(f"{'='*60}")

        docs_to_process = []
        if os.path.exists(trans["essay_path"]):
            docs_to_process.append(("essay", trans["essay_path"], original_essay))
        else:
            print(f"  [SKIP] {trans['essay_path']} not found")

        if os.path.exists(trans["summary_path"]) and original_summary:
            docs_to_process.append(("summary", trans["summary_path"], original_summary))
        else:
            print(f"  [SKIP] Summary not found, skipping")

        for doc_type, trans_path, original_text in docs_to_process:
            print(f"\n  [{lang}] Back-translating {doc_type}...")

            with open(trans_path, "r", encoding="utf-8") as f:
                translated_text = f.read()

            # Back-translate
            back_translation, gen_time = back_translate(translated_text, lang, system_prompt)

            # Save
            bt_filename = f"{doc_type}_bt_{code}_v2.md"
            bt_path = os.path.join(PIPELINE_DIR, bt_filename)
            with open(bt_path, "w", encoding="utf-8") as f:
                f.write(back_translation)
            print(f"  Saved: {bt_path}")

            # Overall similarity
            overall_sim = compute_similarity(original_text, back_translation, embedder)
            print(f"  Overall semantic similarity: {overall_sim:.4f}")

            # Section comparison for essays
            section_scores = []
            if doc_type == "essay":
                section_scores = section_comparison(original_text, back_translation, embedder)
                if section_scores:
                    print(f"  Section similarities: {section_scores}")
                    avg = sum(section_scores) / len(section_scores)
                    print(f"  Average section similarity: {avg:.4f}")
                    low_sections = [(i+1, s) for i, s in enumerate(section_scores) if s < 0.80]
                    if low_sections:
                        print(f"  ⚠ Low-scoring sections: {low_sections}")

            # Log to Delta Lake
            log_to_delta(f"back_translations_v2/{code}", {
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
                "model": "Llama-3.3-70B-Instruct",
                "timestamp": datetime.now().isoformat()
            })

            log_to_delta("audit/pipeline_runs_v2", {
                "run_id": RUN_ID,
                "step": f"back_translate_{doc_type}_{code}",
                "status": "success",
                "timestamp": datetime.now().isoformat()
            })

            results.append({
                "language": lang,
                "document": doc_type,
                "similarity": overall_sim,
                "avg_section": sum(section_scores) / len(section_scores) if section_scores else None,
                "filename": bt_filename
            })

    # Final Report
    print(f"\n{'='*60}")
    print("Back-Translation Audit Report v2")
    print(f"{'='*60}")
    print(f"\n{'Language':<12} {'Document':<10} {'Overall':<10} {'Avg Sec':<10} {'Status':<8} {'File'}")
    print("-" * 70)
    for r in results:
        status = "PASS" if r["similarity"] > 0.85 else "REVIEW" if r["similarity"] > 0.75 else "FAIL"
        avg = f"{r['avg_section']:.4f}" if r['avg_section'] else "N/A"
        print(f"{r['language']:<12} {r['document']:<10} {r['similarity']:.4f}    {avg:<10} [{status}]  {r['filename']}")

    print(f"\nThreshold: >0.85 PASS | 0.75-0.85 REVIEW | <0.75 FAIL")
    print(f"All outputs saved to: {PIPELINE_DIR}")


if __name__ == "__main__":
    main()
