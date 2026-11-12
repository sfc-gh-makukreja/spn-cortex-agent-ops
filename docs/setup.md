# 2. Set up CI/CD

Ask Cortex Code: *"Set up CI/CD for this repo"*. The `setup-cicd` skill does the
following and asks before each change.

| Step | What happens |
|---|---|
| Repo identity | Reads owner/repo and the numeric IDs the OIDC subject needs |
| Bootstrap Snowflake (once, ACCOUNTADMIN) | `bootstrap/setup.sql`: CI warehouse, DCM project home, one deployer role and one OIDC service user per environment, a network policy for GitHub Actions |
| Data access | `aux/data/grant_deployers.sql`: lets DCM pass read access on your data to the audience roles |
| GitHub environments | `dev`, `test`, `prod`, each with `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` variables; reviewers on `test` (engineering) and `prod` (the business) |
| First deploy | Push to `main`; the first run creates `AGENTS_<ENV>`; then `bootstrap/agent.sql` creates the agent once per environment; re-run |

No secrets are stored: each Snowflake CI user trusts exactly one GitHub environment
through OIDC, so only a job running in the approved `prod` environment can log in as
the prod user.

## Prove it

1. Change a line of the agent's instructions in a branch and open a PR. The DCM plan
   is posted as a comment.
2. Merge. **Test** deploys, adds a new agent version, runs the evaluation and puts the
   report on the run page.
3. The business reads the report, tries the change in UAT, and approves **prod**.
4. Run the **Rollback** workflow with the previous release; the `PROD` alias moves back.
