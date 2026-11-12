# 1. Adopt your agent

Open the repo in Cortex Code and ask: *"Adopt my agent `DB.SCHEMA.NAME`"*. The
`adopt-agent` skill runs these steps and asks before it changes anything.

```bash
# 1. Export the agent and each semantic view it uses (agent-studio CLI)
cortex agent-studio agent-read --fqn DEMO_DB.AGENTS.MY_AGENT          # save the YAML
cortex agent-studio sv-read    --fqn DEMO_DB.CORE.ORDERS_SV           # save the YAML

# 2. Normalise to DEV names and write into agent/
uv run ops adopt agent_in.yaml --semantic-view orders.sv.yaml \
    --map DEMO_DB=SALES_DEV --map OLD_AGENT_DB=AGENTS_DEV

# 3. Edit agentops.yml (agent name, data databases, audiences, account), then
uv run ops generate
```

## What `ops adopt` does

- Rewrites database names in the spec and semantic views to the `<NAME>_DEV` form with `--map`.
- Prints a **WARNING** for any tool dependency whose database does not follow the convention.
- Writes `agent/agent.yaml` and `agent/<name>.sv.yaml`. These are always written for DEV; `ops render` rewrites them for TEST and PROD.

## What `ops generate` writes

| File | Contains |
|---|---|
| `dcm/manifest.yml` | One DCM target per environment, each owned by that environment's deployer role |
| `dcm/sources/definitions/platform/agent_home.sql` | `AGENTS_<ENV>` database with `CORE`, `CONTEXT`, `TOOLS` schemas, the spec stage (`SNOWFLAKE_SSE`) and the evaluation stage |
| `dcm/sources/definitions/access/access.sql` | One audience role per environment with exactly the grants the agent's tools need: the agent, semantic views and their base tables, search services, functions and procedures |

!!! info "Why the agent itself is not in DCM"
    DCM does not have a `DEFINE AGENT`. It owns the agent's **home** and its roles and
    grants; the agent is versioned by `ops/release.sql` and `ops/promote.sql`, which
    gives you versions, aliases and rollback.

## Evaluation questions

Write 4 to 8 questions the business cares about in `evals/questions.yml`, each with a
description of what a good answer contains. Do not name tools: describe what good
looks like, not how the agent gets there.
