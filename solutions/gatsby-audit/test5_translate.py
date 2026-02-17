import httpx, json, re, time

TOWER_URL = "http://localhost:8080/v1/chat/completions"

GLOSSARY = """GLOBAL GLOSSARY (use these terms consistently):
- Green Light = luz verde (ES) / 绿灯 (ZH)
- Valley of Ashes = Valle de las Cenizas (ES) / 灰烬之谷 (ZH)
- Doctor T.J. Eckleburg = Doctor T.J. Eckleburg (ES) / T.J.埃克尔堡医生 (ZH)
- Gatsby = Gatsby (ES) / 盖茨比 (ZH)
- Daisy = Daisy (ES) / 黛西 (ZH)
- American Dream = Sueño Americano (ES) / 美国梦 (ZH)
- Jazz Age = Era del Jazz (ES) / 爵士时代 (ZH)
- Old Money = viejo dinero (ES) / 旧钱 (ZH)
- New Money = nuevo dinero (ES) / 新钱 (ZH)
- East Egg = East Egg (ES) / 东卵 (ZH)
- West Egg = West Egg (ES) / 西卵 (ZH)"""

LANG_CONFIG = {
    "Spanish": {
        "user_prefix": f"Translate the following English literary analysis to Spanish.\n{GLOSSARY}\nCitation anchoring: preserve all (Chapter X) references.\nMaintain GS-15 academic register.\n\n",
        "file_suffix": "es"
    },
    "Mandarin": {
        "user_prefix": f"Translate the following English literary analysis to Mandarin Chinese.\n{GLOSSARY}\nCitation anchoring: preserve all (Chapter X) references as (第X章).\nDo NOT use Chengyu idioms. Use modern standard Mandarin.\nMaintain GS-15 academic register.\n\n",
        "file_suffix": "zh"
    }
}

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
    # If no ## headers found, return as single section
    if len(sections) <= 1:
        return [text]
    return sections

def translate_section(text, user_prefix):
    response = httpx.post(TOWER_URL,
        json={
            "model": "tower-plus",
            "messages": [{"role": "user", "content": user_prefix + text}],
            "max_tokens": 4000,
            "temperature": 0.1
        },
        timeout=600
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def translate_document(input_path, lang, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    sections = split_by_headers(text)
    print(f"  [{lang}] {len(sections)} sections from {input_path}")
    
    translated = []
    total_time = 0
    for i, section in enumerate(sections):
        if not section.strip():
            continue
        start = time.time()
        print(f"    Section {i+1}/{len(sections)} ({len(section)} chars)...", end=" ", flush=True)
        result = translate_section(section, LANG_CONFIG[lang]["user_prefix"])
        elapsed = time.time() - start
        total_time += elapsed
        print(f"done ({elapsed:.1f}s)")
        translated.append(result)
    
    full = '\n\n'.join(translated)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full)
    print(f"  Saved {output_path} ({len(full)} chars, {total_time:.1f}s total)")

# Translate all 4 documents
ESSAY = "essay_run-20260216-100158-a5efa3.md"
SUMMARY = "executive_summary_v4.md"

for lang in ["Spanish", "Mandarin"]:
    suffix = LANG_CONFIG[lang]["file_suffix"]
    print(f"\n=== Translating to {lang} ===")
    translate_document(ESSAY, lang, f"essay_{suffix}_v4.md")
    translate_document(SUMMARY, lang, f"summary_{suffix}_v4.md")

print("\n=== All translations complete ===")
