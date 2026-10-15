"""Run after installing tomc-memory from this repository."""

from tomc import compile_memory

result = compile_memory(
    messages="A = 3\nB copies A\nA = 8\nC copies B",
    query="What are the current values?",
    token_budget=128,
    strategy="tomc",
)
print(result.compiled_memory)
print(result.stats)
