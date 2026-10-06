"""Run after installing the core: python examples/snapshot.py. No API needed."""

from tomc import compile_memory

result = compile_memory(
    messages=[
        {"role": "user", "content": "drink = tea\nseat = window"},
        {"role": "user", "content": "backup_drink copies drink"},
        {"role": "user", "content": "drink = decaf tea\nseat = aisle"},
    ],
    query="What are the current drink, backup_drink and seat preferences?",
    token_budget=96,
    strategy="tomc",
)
print(result.compiled_memory)
print(f"Estimated tokens: {result.stats.input_tokens} -> {result.stats.output_tokens}")
print("This tiny example shows snapshot semantics; provenance adds overhead.")
