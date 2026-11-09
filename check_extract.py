from memory_engine.llm import CohereLLM

llm = CohereLLM()

texts = [
    "Priya is the owner of the billing migration. The deadline is Oct 20. We decided to use Stripe for payments.",
    "Quick update: the billing migration deadline moved to Nov 3, and Rahul is taking over the migration from Priya.",
    "Hey! How are you? Hope the weekend was good.",
]

for t in texts:
    print("\nTEXT:", t)
    for f in llm.extract_facts(t):
        print("  -", f["subject"], "|", f["fact"])
