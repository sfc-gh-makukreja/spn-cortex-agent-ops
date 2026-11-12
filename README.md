# Cortex Agent Ops

A template that takes a Cortex Agent you already have and ships it through **dev, test
and prod**: Git for every change, an evaluation against what the business calls a good
answer, approval gates that move from engineering to the business, and a release you can
roll back by moving an alias.

Docs: https://sfc-gh-makukreja.github.io/spn-cortex-agent-ops/

## Bring any agent

Built in Snowsight, from a spec YAML, with the `agent-studio` skill, or by
[spn-demo-creator](https://github.com/sfc-gh-makukreja/spn-demo-creator). Your data is
out of scope: follow the [naming convention](docs/naming.md).

## Three steps

1. **Adopt**: `adopt-agent` skill (or `uv run ops adopt ...` then `uv run ops generate`)
2. **Set up CI/CD**: `setup-cicd` skill (bootstrap, GitHub environments, OIDC, first deploy)
3. **Ship**: PR, merge, read the evaluation, approve prod. Roll back with one workflow.

```
agentops.yml                 the one config you edit
agent/                       adopted spec + semantic views, written with DEV names
dcm/                         generated: manifest, agent home, audience roles and grants
ops/                         ops CLI; release, promote, evaluate, eval report SQL
evals/questions.yml          business-owned questions and what a good answer contains
bootstrap/                   one-time Snowflake setup and one-time agent creation
aux/data/                    optional helpers for the data naming convention
.github/workflows/           pr, main (test then prod), rollback, docs
.agents/skills/              adopt-agent, setup-cicd
```

Credit: the lifecycle and patterns come from Srini and Neel's agent lifecycle lab.
