import os
from memory_engine import MemoryEngine
from memory_engine.llm import CohereLLM

if os.path.exists("check.db"):
    os.remove("check.db")

eng = MemoryEngine(CohereLLM(), db_path="check.db")
user = "aswin"

eng.add(user, "Priya is the owner of the billing migration. The deadline is Oct 20. We decided to use Stripe for payments.", timestamp="2026-10-01")
eng.add(user, "Quick update: the billing migration deadline moved to Nov 3, and Rahul is taking over the migration from Priya.", timestamp="2026-10-08")

print("\n--- ALL FACTS ---")
for f in eng.list_facts(user):
    print(f"#{f['id']} [{f['created_at'][:10]}] {f['status']:<10} {f['fact']}")

for q in ["When is the billing migration deadline?", "Who owns the billing migration?"]:
    print("\nQ:", q)
    for h in eng.search(user, q, top_k=3):
        print(f"  score={h['score']}  sim={h['similarity']}  {h['fact']}")
