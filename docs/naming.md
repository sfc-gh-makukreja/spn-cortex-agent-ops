# Naming convention and data

The template does not create, load or manage your data. It assumes the objects below
exist and follows these names, so a spec written once for DEV can be rendered for TEST
and PROD (`<NAME>_DEV` becomes `<NAME>_TEST` or `<NAME>_PROD`).

## What you bring

| Object | Name | Notes |
|---|---|---|
| Data database | `<NAME>_<ENV>` | Tables, documents and Cortex Search services the agent reads. One per environment: `SALES_DEV`, `SALES_TEST`, `SALES_PROD`. List the `<NAME>` part in `data_databases` in `agentops.yml`. |
| Data inside | Same schemas, tables and search service names in every environment | The semantic view and agent refer to them by the DEV name; only the database suffix changes. |
| Custom tool functions / procedures | Live in a data database or `AGENTS_<ENV>.TOOLS` | Referenced in the spec by fully qualified name. |

## What the template creates

| Object | Name |
|---|---|
| Agent home | `AGENTS_<ENV>` with schemas `CORE` (agent, spec stage, evaluation config), `CONTEXT` (semantic views) and `TOOLS` |
| Agent | `AGENTS_<ENV>.CORE.<AGENT_NAME>`, same name in every environment |
| Spec stage | `AGENTS_<ENV>.CORE.AGENT_SPECS` (must be `SNOWFLAKE_SSE`) |
| Evaluation | `AGENTS_<ENV>.CORE.EVAL_CONFIG` stage and `<AGENT>_TEST_QUESTIONS` table |
| Deployer role | `AGENTOPS_DEPLOYER_<ENV>`: owns the environment, used by CI |
| CI user | `AGENTOPS_CI_<ENV>`: OIDC, trusts one GitHub environment |
| Audience role | `<AGENT>_<ENV>_USER`: granted to the users in `audiences` |
| Warehouse | `AGENTOPS_CI_WH` (configurable) |
| DCM project | `<dcm_database>.<dcm_schema>.AGENTOPS_<ENV>` |

## Optional helper scripts (`aux/data/`)

| Script | When to use |
|---|---|
| `clone_environments.sql` | You have `<NAME>_DEV` and want `_TEST` and `_PROD` as clones (with data) or structure-only copies. Cortex Search services must be recreated per environment. |
| `grant_deployers.sql` | Always, once your data databases exist: lets DCM pass read access on your data to the audience roles. |

!!! tip "Production data"
    TEST should look like production (it is UAT). PROD should hold real data. If DEV
    holds synthetic data, use `with_data=false` for PROD and load the real data yourself.
