---
name: adopt-agent
description: Adopt an existing Cortex Agent (built in the UI, by spec YAML, with agent-studio or with spn-demo-creator) into this repo so it can ship through dev, test and prod. Triggers - adopt agent, import my agent, put my agent in CI/CD, bring my agent into the repo, productionise agent, agent ops.
---

# Adopt an existing Cortex Agent

Takes an agent that already works and writes it into this repo with DEV names, then
generates the DCM environment definitions. Use the `ops` CLI and
`cortex agent-studio`; do not hand-write `CREATE AGENT` or use `DESCRIBE AGENT` to
extract a spec.

## Rules
- Specs and semantic views in this repo are always written with **DEV** names
  (`<NAME>_DEV`, `AGENTS_DEV`). `ops render` rewrites them per environment.
- The data is out of scope. Never create or load data tables here. If the source
  data does not follow the naming convention, tell the user to read `docs/naming.md`
  and offer `aux/data/clone_environments.sql`.
- Ask before running anything that changes Snowflake.

## Steps

1. **Identify the agent.** Ask for `DATABASE.SCHEMA.AGENT_NAME`. If only a name is
   given: `SHOW AGENTS LIKE '%<NAME>%' IN ACCOUNT;`

2. **Export it.** Use the agent-studio CLI:
   ```bash
   cortex agent-studio agent-read --fqn <DB>.<SCHEMA>.<AGENT>
   ```
   Save the YAML it returns to a scratch file (not in the repo), e.g. `/tmp/agent_in.yaml`.

3. **Export each semantic view the agent uses.** List them with `uv run ops deps`
   (after step 4) or read `tool_resources` in the spec, then:
   ```bash
   cortex agent-studio sv-read --fqn <DB>.<SCHEMA>.<SEMANTIC_VIEW>
   ```
   Save each to a scratch file.

4. **Adopt.** Map the source database names to the convention. Example:
   ```bash
   uv run ops adopt /tmp/agent_in.yaml \
     --semantic-view /tmp/orders.sv.yaml \
     --map DEMO_DB=SALES_DEV --map OLD_AGENT_DB=AGENTS_DEV
   ```
   It writes `agent/agent.yaml` and `agent/<name>.sv.yaml`, and prints a WARNING for
   any dependency whose database does not follow `<NAME>_DEV`. Fix warnings with more
   `--map` flags or by adding the database to `data_databases` in `agentops.yml`.

5. **Fill in `agentops.yml`**: agent name, display name, `data_databases` (the
   `<NAME>` part of each `<NAME>_DEV`), `audiences`, Snowflake account, and the
   `semantic_views` paths.

6. **Generate the environment definitions:**
   ```bash
   uv run ops generate
   ```
   This writes `dcm/manifest.yml`, `dcm/sources/definitions/platform/agent_home.sql`
   and `dcm/sources/definitions/access/access.sql` (one audience role per environment
   with exactly the grants the agent's tools need). Show the user `access.sql` and
   confirm it before moving on.

7. **Evaluation questions.** Ask the user for 4 to 8 questions the business cares about,
   each with a description of what a good answer contains. Write them to
   `evals/questions.yml`:
   ```yaml
   questions:
     - question: "..."
       good_answer: "A good answer finds ... A poor answer ..."
   ```
   If the agent came from `spn-demo-creator`, turn its sample questions into this file.

8. Hand off to the `setup-cicd` skill.

## Verify
- `uv run pytest -q` passes.
- `uv run ops render agent/agent.yaml TEST` prints valid YAML with `_TEST` names.
- `uv run ops deps` lists every semantic view, search service and tool the agent uses.
