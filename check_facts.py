import sys
from memory_engine import MemoryEngine

user = sys.argv[1]
eng = MemoryEngine(None, db_path="eval.db")
for f in eng.list_facts(user):
    print(f"#{f['id']} {f['status']:<10} [{f['subject']}] {f['fact']}")
