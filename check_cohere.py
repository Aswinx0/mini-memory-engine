from memory_engine.llm import CohereLLM

llm = CohereLLM()

print("CHAT:", llm._chat("Reply with exactly one word: hello"))

vec = llm.embed_query("who owns the billing migration?")
print("EMBED: length =", len(vec), "first 3 =", vec[:3])
