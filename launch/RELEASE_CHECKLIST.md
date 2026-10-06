# Release readiness

This is a preparation checklist, not permission to publish. The project remains private until the owner explicitly says “可以公开”. A completed local artifact does not imply it is configured on a platform or tested by users.

## Prepared in this iteration

- [x] Evidence-based UX critique and phased [launch plan](PLAN_ZH.md).
- [x] Default context handoff and assistant setup, with guided tour, complete workbench and research evidence.
- [x] Real snapshot example and source inspector; explicit short-input overhead.
- [x] English/Chinese launch drafts, Show HN draft and recording storyboard.
- [x] Reusable SVG/PNG share card, compact screenshots and readable HTML plan.
- [x] Newcomer feedback templates and a private pilot task sheet.

Validation evidence is recorded in [validation](../docs/validation.md), with exact revision and hosted status in the final staging receipt kept locally under ignored `outputs/`. The release manifest records the actual distributable file hashes. Generated images are prepared, not proof that GitHub's social preview is configured.

## Before choosing T0

- [ ] Author approves final scope, title, author list, citation and public paper URL (or explicitly launches software without a paper link).
- [ ] Five invited, consenting target users complete the [pilot](PILOT_ZH.md); record actual results. Invitation requires the author's separate action/authorization.
- [ ] Resolve first-use blockers; aim for at least 4/5 successful key tasks. This is a planning threshold, not an observed pass rate.
- [ ] Record and review the real 30-second video; add captions/transcript.
- [ ] Author reserves launch-day response time and chooses dates. Suggested capacity: 2 hours at launch, 30 minutes/day for the first week; no public SLA promised.
- [ ] Author explicitly authorizes GitHub/HF publication. PyPI and promotional posting remain separate actions requiring explicit scope.

## At approved publication

- [ ] Re-run CI, artifact hashes, licenses/claims and credential/history scan on the release revision.
- [ ] Change only the approved GitHub and HF repositories to public; verify anonymously in a clean browser.
- [ ] Replace private-staging wording and manifest visibility with actual approved status; do not preemptively remove the staging labels.
- [ ] Check demo cold start, local install, links, mobile evidence inspector and feedback forms.
- [ ] Configure GitHub social preview with `assets/social_preview.png` (1280×640, under 1 MB); verify actual link preview separately.
- [ ] Verify repository description, topics and homepage; no framework logos or integrations without working examples.
- [ ] Create release tag/notes only for the revision being published; use software citation until paper metadata is finalized.
- [ ] Post only the channel/text separately approved by the author, after rechecking that community's rules.

Suggested GitHub description: `A plug-in memory module for your existing LLM API. CPU construction, source-linked records, and selected source text.`

Suggested topics: `llm-memory`, `long-context`, `context-compression`, `llm`, `reproducibility`, `python`. These are prepared suggestions; they are not a claim about platform configuration.

## After launch

- [ ] Record platform-native traffic aggregates at day 1, 3, 7 and 14. Do not infer user-level conversion across anonymous systems.
- [ ] Triage installation failures and incorrect state/provenance before feature requests.
- [ ] Acknowledge issues within available maintainer capacity; label reproduced / needs synthetic example / method boundary.
- [ ] Fix and publish the smallest repeatable blocker. If a release breaks basic use, pause promotion and restore the previously tested revision through a new revert commit; do not rewrite user-visible history.
- [ ] Share an update only when it contains a real fix, reproducible new example or new evidence.

If traffic exceeds the Space's queue capacity, link the verified local run instructions, capture the failure without user payloads and pause additional promotion until service is usable. No paid scaling is authorized by this checklist.
