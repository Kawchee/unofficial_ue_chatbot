from dotenv import load_dotenv
import os
from supabase import create_client
from pathlib import Path

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# Documenti in Supabase
docs = supabase.table("documents").select("id, name, language").execute().data
chunks = supabase.table("chunks").select("document_id").execute().data

# Conta chunk per documento
chunk_counts = {}
for c in chunks:
    chunk_counts[c["document_id"]] = chunk_counts.get(c["document_id"], 0) + 1

# Controlla duplicati
names = [d["name"] for d in docs]
duplicates = [n for n in names if names.count(n) > 1]

print("=== DOCUMENTI IN SUPABASE ===")
for d in sorted(docs, key=lambda x: x["name"]):
    count = chunk_counts.get(d["id"], 0)
    print(f"  {d['name']:<60} | {d['language']} | {count} chunk")

print()
print(f"Totale documenti: {len(docs)}")
print(f"Totale chunk: {len(chunks)}")
print()

if duplicates:
    print(f"DUPLICATI TROVATI: {set(duplicates)}")
else:
    print("Nessun duplicato.")

print()

# File in data/raw
raw_files = {f.name for f in Path("data/raw").iterdir() if f.suffix.lower() in {".pdf", ".txt", ".md"}}
db_names = set(names)

only_in_raw = raw_files - db_names
only_in_db = db_names - raw_files

if only_in_raw:
    print("In data/raw ma NON in Supabase:")
    for f in sorted(only_in_raw):
        print(f"  - {f}")
else:
    print("Tutti i file raw sono in Supabase.")

print()

if only_in_db:
    print("In Supabase ma NON in data/raw:")
    for f in sorted(only_in_db):
        print(f"  - {f}")
else:
    print("Nessun documento orfano in Supabase.")
