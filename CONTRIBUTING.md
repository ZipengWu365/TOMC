# Contributing

Install with `make install`, then run `make test lint security-scan`. Core compilation must remain usable without network access or third-party models.

A method change needs a small example showing its intended semantics. Preserve snapshot-copy dependencies, source order, honest tokenizer accounting, whole-record budgets, and explicit fallback behavior. Add a behavioral test when these contracts change. Do not reformat the preserved files under `src/tomc/_vendor`; extend the public adapter layer and document any differences from the frozen kernels.

Use original synthetic test data. Do not include benchmark text, API responses, credentials or model weights. Update `docs/method.md`, run `make reproduce-results build-docs`, and regenerate `make manifest` for changes to release files. Result claims must remain attached to their evaluation configuration and negative results.

An optional integration should fail clearly when unavailable. It must not return another algorithm's output under the requested method's name. Keep any model download and paid API invocation explicit. Submit a focused pull request explaining the behavior and validation.
