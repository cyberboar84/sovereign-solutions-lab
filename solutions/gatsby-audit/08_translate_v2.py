#!/usr/bin/env python3
"""
Step 08: Translation Pipeline v2
- Translates essay and executive summary to Spanish and Mandarin
- Per-section translation to stay within Tower's 4096 context window
- Improved prompts with name handling and metaphor preservation
- Logs to Delta Lake
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
RUN_ID = f"translate-v2-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

ESSAY_PATH = "./essay_run-20260214-150657-bcf43f.md"
SUMMARY_PATH = "./executive_summary_v3.md"
OUTPUT_DIR = "."

MINIO_STORAGE = {
    "endpoint_url": "http://10.10.10.2:30900",
    "access_key_id": os.getenv("MINIO_ACCESS_KEY", "minio_user"),
    "secret_access_key": os.getenv("MINIO_SECRET_KEY", "PLACEHOLDER_KEY"),
    "region": "us-east-1",
    "allow_http": "true"
}

DELTA_BASE = "s3://sovereign-lakehouse/gatsby-pipeline"

LANGUAGES = {
    "Spanish": {
        "code": "es",
        "system": (
            "You are a world-class literary translator specializing in 20th-century American prose.\n\n"
            "GLOBAL GLOSSARY — Use these translations CONSISTENTLY across all sections:\n"
            "- Green Light = la luz verde\n"
            "- Valley of Ashes = el Valle de las Cenizas\n"
            "- The Eyes of Doctor T.J. Eckleburg = los ojos del Doctor T.J. Eckleburg\n"
            "- The American Dream = el Sueño Americano\n"
            "- The Defunct Mantelpiece Clock = el reloj de chimenea averiado\n"
            "- The Uncut Books = los libros sin abrir\n"
            "- Boats Against the Current = botes contra la corriente\n"
            "- The Death Car / Yellow Car = el auto amarillo / el auto de la muerte\n"
            "- The Fresh, Green Breast of the New World = el fresco y verde pecho del Nuevo Mundo\n"
            "- Jazz Age = la Era del Jazz\n"
            "- Old Money / New Money = viejo dinero / nuevo dinero\n\n"
            "STRICT RULES:\n"
            "1. Preserve ALL Markdown formatting (## headers, *italics*) exactly.\n"
            "2. Keep all citations in English exactly as-is: (Chapter 2), (Chapter IX), (Chapter III).\n"
            "3. Keep proper names in their original English form: Fitzgerald, Gatsby, Daisy, "
            "Tom Buchanan, Nick Carraway, Myrtle Wilson, Doctor T.J. Eckleburg, George Wilson, Jordan Baker.\n"
            "4. CITATION ANCHOR: Text within quotation marks is a direct quote from the 1925 novel. "
            "Provide a strictly literal, word-for-word translation of these quotes. Do NOT use existing "
            "published Spanish translations. Translate directly from the English provided.\n"
            "5. Maintain GS-15 academic register. Do NOT simplify vocabulary. "
            "Translate advanced terms literally (e.g., 'meretricious'='meretriz/meretricio', "
            "'quixotic'='quijotesco', 'ephemeral'='efímero', 'stratification'='estratificación').\n"
            "6. Do NOT truncate. Translate the COMPLETE text.\n"
            "7. Do NOT add any translator's notes, explanations, or commentary."
        ),
        "user_prefix": "Translate the following scholarly literary analysis into Spanish. "
                        "Preserve the academic tone and metaphorical nuances of the original.\n\nSource Text:\n"
    },
    "Mandarin": {
        "code": "zh",
        "system": (
            "You are a world-class literary translator specializing in 20th-century American prose.\n\n"
            "GLOBAL GLOSSARY — Use these translations CONSISTENTLY across all sections:\n"
            "- Green Light = 绿灯\n"
            "- Valley of Ashes = 灰烬之谷\n"
            "- The Eyes of Doctor T.J. Eckleburg = T.J.埃克尔堡医生的眼睛\n"
            "- The American Dream = 美国梦\n"
            "- The Defunct Mantelpiece Clock = 壁炉台上坏掉的钟\n"
            "- The Uncut Books = 未裁开的书\n"
            "- Boats Against the Current = 逆流而上的船\n"
            "- The Death Car / Yellow Car = 黄色汽车 / 死亡之车\n"
            "- The Fresh, Green Breast of the New World = 新世界那鲜嫩翠绿的胸脯\n"
            "- Jazz Age = 爵士时代\n"
            "- Old Money / New Money = 旧钱 / 新钱\n"
            "- The Great Gatsby = 了不起的盖茨比\n\n"
            "STRICT RULES:\n"
            "1. Preserve ALL Markdown formatting (## headers, *italics*) exactly.\n"
            "2. Keep all citations in English exactly as-is: (Chapter 2), (Chapter IX), (Chapter III).\n"
            "3. Use standard literary Chinese translations for proper names: "
            "Gatsby=盖茨比, Daisy=黛西, Fitzgerald=菲茨杰拉德, Tom Buchanan=汤姆·布坎南, "
            "Nick Carraway=尼克·卡拉韦, Myrtle Wilson=默特尔·威尔逊, George Wilson=乔治·威尔逊, "
            "Jordan Baker=乔丹·贝克, Doctor T.J. Eckleburg=T.J.埃克尔堡医生.\n"
            "4. CITATION ANCHOR: Text within quotation marks is a direct quote from the 1925 novel. "
            "Provide a strictly literal, word-for-word translation of these quotes. Do NOT use existing "
            "published Chinese translations of Gatsby. Translate directly from the English provided.\n"
            "5. Do NOT use Chengyu (成语) or Chinese idioms to replace Fitzgerald's specific 1920s imagery. "
            "Maintain a 'foreignizing' translation strategy — preserve the Western literary voice.\n"
            "6. Maintain GS-15 academic register. Do NOT simplify vocabulary. "
            "Translate advanced terms literally (e.g., 'meretricious'='华而不实的', "
            "'quixotic'='唐吉诃德式的', 'ephemeral'='短暂的', 'stratification'='阶层分化').\n"
            "7. Do NOT truncate. Translate the COMPLETE text.\n"
            "8. Do NOT add any translator's notes, explanations, or commentary."
        ),
        "user_prefix": "Translate the following scholarly literary analysis into Mandarin Chinese (简体中文). "
                        "Preserve the academic tone and metaphorical nuances of the original.\n\nSource Text:\n"
    }
}

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


def split_into_sections(text, max_chunk_words=400):
    """Split text by ## headers. Fall back to paragraph chunking."""
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

    # If only 1 section (no headers found), chunk by paragraphs
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


def translate_text(text, system_prompt, user_prefix):
    """Translate text section-by-section via TowerLLM."""
    # Short text (summary) — translate in one shot
    if len(text.split()) < 400:
        sections = [text]
    else:
        sections = split_into_sections(text)

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

    full_translation = "\n\n".join(translated_sections)
    return full_translation, total_time


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"{'='*60}")
    print(f"Translation Pipeline v2")
    print(f"Run ID: {RUN_ID}")
    print(f"{'='*60}")

    # Load source texts
    with open(ESSAY_PATH, "r") as f:
        essay = f.read()

    summary_exists = os.path.exists(SUMMARY_PATH)
    summary = ""
    if summary_exists:
        with open(SUMMARY_PATH, "r") as f:
            summary = f.read()

    print(f"\nEssay: {len(essay.split())} words")
    if summary_exists:
        print(f"Summary: {len(summary.split())} words")
    else:
        print("Summary: not found, skipping")

    documents = {"essay": essay}
    if summary_exists and summary.strip():
        documents["summary"] = summary

    for lang_name, lang_config in LANGUAGES.items():
        print(f"\n{'='*60}")
        print(f"Translating to {lang_name}")
        print(f"{'='*60}")

        for doc_name, doc_text in documents.items():
            print(f"\n  [{lang_name}] Translating {doc_name}...")

            translation, gen_time = translate_text(
                doc_text,
                lang_config["system"],
                lang_config["user_prefix"]
            )

            # Save .md file
            filename = f"{doc_name}_{lang_config['code']}_v2.md"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(translation)
            print(f"  Saved: {filepath}")

            # Log to Delta Lake
            log_to_delta(f"translations_v2/{lang_config['code']}", {
                "run_id": RUN_ID,
                "document": doc_name,
                "language": lang_name,
                "language_code": lang_config["code"],
                "source_word_count": len(doc_text.split()),
                "translated_word_count": len(translation.split()),
                "content": translation,
                "generation_time_seconds": round(gen_time, 2),
                "model": "TowerInstruct-13B-v0.1-Q6_K",
                "timestamp": datetime.now().isoformat()
            })

            log_to_delta("audit/pipeline_runs_v2", {
                "run_id": RUN_ID,
                "step": f"translate_{doc_name}_{lang_config['code']}",
                "status": "success",
                "timestamp": datetime.now().isoformat()
            })

    # Summary
    print(f"\n{'='*60}")
    print("Translation Complete!")
    print(f"{'='*60}")
    print(f"\nOutput files:")
    for lang_name, lang_config in LANGUAGES.items():
        for doc_name in documents:
            filename = f"{doc_name}_{lang_config['code']}_v2.md"
            filepath = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    wc = len(f.read().split())
                print(f"  {filename}: {wc} words")


if __name__ == "__main__":
    main()
