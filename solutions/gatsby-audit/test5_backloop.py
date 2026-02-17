import httpx, json, re, time
import numpy as np

LLAMA_URL = "http://localhost:8080/v1/chat/completions"

SYSTEM_PROMPT_ES = """You are a Philological Auditor performing translation quality control.
Translate the following Spanish text to English as literally as possible.
Preserve exact structure and word order where possible.
Do NOT correct or improve awkward phrasing -- preserve it.
Keep all Markdown headers and citations exactly as-is.
Do NOT add translator notes or meta-text."""

SYSTEM_PROMPT_ZH = """You are a Philological Auditor performing translation quality control.
Translate the following Mandarin Chinese text to English as literally as possible.
Preserve exact structure and word order where possible.
Do NOT correct or improve awkward phrasing -- preserve it.
If Chengyu idioms were used, translate the idiom literally.
Keep all Markdown headers and citations exactly as-is.
Do NOT add translator notes or meta-text."""

def split_by_headers(text):
    sections = []
    current = []
    for line in text.split('\n'):
        if line.startswith('## ') and current:
            sections.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append('\n'.join(current))
    if len(sections) <= 1 and len(text) > 3000:
        # Fallback: split by double newline for long unsectioned text
        return [p for p in text.split('\n\n') if p.strip()]
    return sections

def back_translate(text, system_prompt, lang):
    sections = split_by_headers(text)
    print(f"  [{lang}] {len(sections)} sections")
    
    translated = []
    total_time = 0
    for i, section in enumerate(sections):
        if not section.strip():
            continue
        start = time.time()
        chars = len(section)
        print(f"    Section {i+1}/{len(sections)} ({chars} chars)...", end=" ", flush=True)
        
        response = httpx.post(LLAMA_URL,
            json={
                "model": "llama-3.3",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": section}
                ],
                "max_tokens": 2000,
                "temperature": 0.1
            },
            timeout=600
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]
        elapsed = time.time() - start
        total_time += elapsed
        print(f"{len(result.split())} words, {elapsed:.1f}s")
        translated.append(result)
    
    return '\n\n'.join(translated), total_time

# Back-translate all 4
docs = [
    ("Spanish Essay", "essay_es_v4.md", "essay_bt_es_v4.md", SYSTEM_PROMPT_ES),
    ("Spanish Summary", "summary_es_v4.md", "summary_bt_es_v4.md", SYSTEM_PROMPT_ES),
    ("Mandarin Essay", "essay_zh_v4.md", "essay_bt_zh_v4.md", SYSTEM_PROMPT_ZH),
    ("Mandarin Summary", "summary_zh_v4.md", "summary_bt_zh_v4.md", SYSTEM_PROMPT_ZH),
]

for label, src, dst, prompt in docs:
    print(f"\n=== Back-translating: {label} ===")
    with open(src, 'r', encoding='utf-8') as f:
        text = f.read()
    bt, gen_time = back_translate(text, prompt, label)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(bt)
    print(f"  Saved {dst} ({len(bt.split())} words, {gen_time:.1f}s)")

# Score all
print("\n\n" + "=" * 65)
print("Back-Translation Audit - Test 5 (Final)")
print("=" * 65)

from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-large-en-v1.5', device='cpu')

ESSAY_ORIG = "essay_run-20260216-100158-a5efa3.md"
SUMMARY_ORIG = "executive_summary_v4.md"

score_pairs = [
    ("Spanish Essay", ESSAY_ORIG, "essay_bt_es_v4.md"),
    ("Spanish Summary", SUMMARY_ORIG, "summary_bt_es_v4.md"),
    ("Mandarin Essay", ESSAY_ORIG, "essay_bt_zh_v4.md"),
    ("Mandarin Summary", SUMMARY_ORIG, "summary_bt_zh_v4.md"),
]

print(f"{'Document':<25} {'RTSF':>8} {'Status':>10}")
print("-" * 65)
for label, orig_path, bt_path in score_pairs:
    with open(orig_path, 'r', encoding='utf-8') as f:
        orig = f.read()
    with open(bt_path, 'r', encoding='utf-8') as f:
        bt = f.read()
    emb_orig = model.encode(orig, normalize_embeddings=True)
    emb_bt = model.encode(bt, normalize_embeddings=True)
    sim = float(np.dot(emb_orig, emb_bt))
    status = 'PASS' if sim > 0.85 else 'REVIEW' if sim > 0.75 else 'FAIL'
    print(f"{label:<25} {sim:>8.4f} {'['+status+']':>10}")
print("=" * 65)
