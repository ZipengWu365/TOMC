# Data and licensing

## Project material

Project code and original synthetic examples use the MIT License. They are free to use for research, teaching, personal and commercial purposes, including modification, redistribution and closed-source integration. Copies or substantial portions of the software must retain the copyright and license notice. The root `LICENSE` contains the license text and the author's copyright notice.

Research citation through `CITATION.cff` is encouraged, not an additional license condition. Feedback, contributions and collaboration are welcome at zxw365@student.bham.ac.uk.

The copyright holder authorized the change from PolyForm Noncommercial 1.0.0 to MIT on 2026-10-10. Current MIT-licensed [assistant packages](https://github.com/ZipengWu365/TOMC/tree/main/plugins/downloads) include the new license. Earlier tags and release assets retain their original embedded notices and are preserved as historical snapshots; use the current source or MIT packages for the updated distribution. This change does not relicense third-party dependencies, datasets, model weights or provider marks.

The supplied paper reference and three archived research files retain their original bytes. `SOURCE_PROVENANCE.json` records their origins and hashes. The [legacy compatibility extension](legacy_extensions.md) is documented separately from the paper method. Selected manuscript figures were approved for this repository and have separate source hashes. Provider and method marks belong to their owners and do not imply endorsement.

The release includes no manuscript PDF, benchmark text, third-party repository source or model weights. `THIRD_PARTY_LOCK.json` records reviewed upstream revisions, licenses and integration decisions.

## Evidence exports

`DATA_PROVENANCE.md` maps the bundled synthetic examples and aggregate tables. The current snapshot contains BEAM/RULER scores, reader-input measurements and construction resources. Its arithmetic can be verified offline.

The historical four-reader export also includes numeric conversation sums for reconstructing effects and confidence intervals. It excludes prompts, answers and original identifiers. Source hashes identify private artifacts without publishing their contents.

Archived boundary summaries retain approved findings but omit original evidence-location columns. Exported aggregates are distinct from user-generated runtime files.

## Dependencies

LLMLingua declares MIT; the optional adapter calls the installed official package. Model weights must be reviewed under each model card's own license.

Selective Context's README declares MIT, but its linked license file was unavailable during the recorded review. No integration is bundled. Mem0 and Letta declare Apache-2.0 and are not dependencies. Gradio is Apache-2.0 and is installed through its distributor.

`DEPENDENCY_LICENSES.json` records declared license metadata for the 55-package Gradio dependency closure in the staging Python 3.12 environment. The hash-bearing demo lockfile records a Python 3.10-compatible resolution. Dependency source and wheel contents are not included in this Git repository.

## Your data and release status

Runtime exports in `outputs/` can contain your original text and evidence. Keep those files private when your inputs are private. The local MCP notebook also stores submitted text in plaintext; see [assistant setup](assistant_setup.md).

Release exclusions cover credentials, environment files, private endpoints, reader/judge payloads, original benchmark questions and answers, invalid experiment payloads, caches and virtual environments. The complete list is in `EXCLUSIONS.md`.

The GitHub repository is currently private. Changing visibility or publishing to PyPI is a separate release decision. The release manifest inventories distributable files; credential, history and file-size scans check that inventory. Those checks do not anonymize future user inputs.
