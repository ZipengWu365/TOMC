# Legacy compatibility extension

The optional `strategy="tomc2"` adapter is retained for existing integrations. It is an archived software-trace compiler, separate from the TOMC paper and its BEAM/RULER evaluation. The historical identifier does not denote a second version of the paper's method.

Current defaults and automatic routing do not select this adapter. Use it only through an explicit strategy argument when maintaining an existing integration:

```python
from tomc import compile_memory

result = compile_memory(
    messages="Goal: fix the parser\npytest: test_parse failed",
    query="What happened in this trace?",
    token_budget=256,
    strategy="tomc2",
)
```

The adapter extracts goals, repository observations, attempts, test/error reports, facts, verifier suggestions and next actions with keyword rules. It reserves 70% of the memory budget for compiled sections and uses remaining space for the newest fitting source rows.

These entries describe the submitted trace. TOMC does not run the suggested commands or verify their results. A failure mention can remain after a later success; negation and ambiguous reports can mislead the rules. Long observations may be clipped, and earlier sections can leave later rows outside the budget. Generic suggestions carry `basis=heuristic_prior`; check `included` and the supporting sources.

The source files `src/tomc/_vendor/tomc2.py`, `types.py` and `utils.py` retain their provenance and original identifiers. [Source hashes](SOURCE_PROVENANCE.json) record their origins. This compatibility path supplies no additional paper result.
