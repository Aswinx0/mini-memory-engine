from memory_engine import MemoryEngine

eng = MemoryEngine(None, db_path="eval.db")
for f in eng.list_facts("billing"):
    print(f"#{f['id']} {f['status']:<10} [{f['subject']}] {f['fact']}")
