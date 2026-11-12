# Tasks

## Done
- [x] Repo scaffold, `agentops.yml` single config
- [x] `ops` CLI: adopt, generate, render, semantic-view, deps, eval-dataset, eval-config, sql (6 tests pass)
- [x] Adopt-agent and setup-cicd skills
- [x] Bootstrap SQL, release/promote/evaluate/eval_report SQL
- [x] Workflows: pr, main, _deploy, rollback, docs
- [x] Aux data scripts, docs from the lifecycle slides

## Todo
- [ ] End-to-end test on DEMO-PAT with a spn-demo-creator agent (adopt, dev/test/prod, promote, rollback)
- [ ] `mkdocs build --strict` passes
- [ ] Public repo on sfc-gh-makukreja, Pages enabled

## What worked / failed (do not repeat)
- Worked: `ops sql` wrapper passes args as a list; `$(ops vars)` word splitting broke on display names with spaces.
- Worked: confirmed from docs that DCM supported entities include Semantic view but not Agent.
- Failed: writing an empty `__init__.py` with the Write tool is rejected; use a docstring.
