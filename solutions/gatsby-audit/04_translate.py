#!/usr/bin/env python3
"""
Step 4: Translation Pipeline
- Reads essay and executive summary
- Translates both to Spanish and Mandarin via TowerLLM-13B (llama.cpp)
- Saves .md files locally for review
- Logs everything to Delta Lake (MinIO)
"""

import os
import json
import time
import uuid
from datetime import datetime

import httpx
import pandas as pd
from deltalake import write_deltalake

# =============================================================================
# Configuration
# =============================================================================

TOWER_URL = "http://localhost:8080/v1/chat/completions"
RUN_ID = f"translate-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

ESSAY_PATH = "./essay_run-20260213-171412-1a3870.md"
SUMMARY_PATH = "./executive_summary.md"
OUTPUT_DIR = "."

MINIO_STORAGE = {
    "endpoint_url": "http://10.10.10.2:30900",
    "access_key_id": os.getenv("MINIO_ACCESS_KEY", "minio_user"),
    "secret_access_key": os.getenv("SOV_SECRET_KEY", "placeholder_key"),
    "region": "us-east-1",
    "allow_http": "true"
}

DELTA_BASE = "s3://sovereign-lakehouse/gatsby-pipeline"

LANGUAGES = {
    "Spanish": {
        "code": "es",
        "instruction": "Translate the following English text into Spanish. Preserve all formatting, citations, and academic tone. Output ONLY the Spanish translation, nothing else."
    },
    "Mandarin": {
        "code": "zh",
        "instruction": "Translate the following English text into Mandarin Chinese (简体中文). Preserve all formatting, citations, and academic tone. Output ONLY the Chinese translation, nothing else."
    }
}

# =============================================================================
# Helpers
# =============================================================================

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


def translate_text(text, language, instruction, max_chunk_words=800):
    """
    Translate text via TowerLLM. For long texts, split into sections
    and translate section by section to stay within context window.
    """
    # Split by section headers (## )
    sections = []
    current_section = []
    for line in text.split("\n"):
        if line.startswith("## ") and current_section:
            sections.append("\n".join(current_section))
            current_section = [line]
        else:
            current_section.append(line)
    if current_section:
        sections.append("\n".join(current_section))

    # If text is short enough (summary), translate in one shot
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
                TOWER_URL,
                json={
                    "model": "tower",
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

    full_translation = "\n\n".join(translated_sections)
    return full_translation, total_time


# =============================================================================
# Main Pipeline
# =============================================================================

def main():
    print(f"{'='*60}")
    print(f"Translation Pipeline")
    print(f"Run ID: {RUN_ID}")
    print(f"{'='*60}")

    # Load source texts
    with open(ESSAY_PATH, "r") as f:
        essay = f.read()
    with open(SUMMARY_PATH, "r") as f:
        summary = f.read()

    print(f"\nEssay: {len(essay.split())} words")
    print(f"Summary: {len(summary.split())} words")

    documents = {
        "essay": {"text": essay, "path_prefix": "essay"},
        "summary": {"text": summary, "path_prefix": "summary"}
    }

    for lang_name, lang_config in LANGUAGES.items():
        print(f"\n{'='*60}")
        print(f"Translating to {lang_name}")
        print(f"{'='*60}")

        for doc_name, doc_info in documents.items():
            print(f"\n  [{lang_name}] Translating {doc_name}...")

            translation, gen_time = translate_text(
                doc_info["text"],
                lang_name,
                lang_config["instruction"]
            )

            # Save .md file
            filename = f"{doc_info['path_prefix']}_{lang_config['code']}.md"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(translation)
            print(f"  Saved: {filepath}")

            # Log to Delta Lake
            log_to_delta(f"translations/{lang_config['code']}", {
                "run_id": RUN_ID,
                "document": doc_name,
                "language": lang_name,
                "language_code": lang_config["code"],
                "source_word_count": len(doc_info["text"].split()),
                "translated_word_count": len(translation.split()),
                "content": translation,
                "generation_time_seconds": round(gen_time, 2),
                "model": "TowerInstruct-13B-v0.1-Q6_K",
                "timestamp": datetime.now().isoformat()
            })

            # Log audit
            log_to_delta("audit/pipeline_runs", {
                "run_id": RUN_ID,
                "step": f"translate_{doc_name}_{lang_config['code']}",
                "config_version": 1,
                "sections_loaded": 0,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            })

    # Summary of outputs
    print(f"\n{'='*60}")
    print("Translation Complete!")
    print(f"{'='*60}")
    print(f"\nOutput files:")
    for lang_name, lang_config in LANGUAGES.items():
        for doc_name, doc_info in documents.items():
            filename = f"{doc_info['path_prefix']}_{lang_config['code']}.md"
            filepath = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    wc = len(f.read().split())
                print(f"  {filename}: {wc} words")


if __name__ == "__main__":
    main()
