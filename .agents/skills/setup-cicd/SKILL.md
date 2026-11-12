---
name: setup-cicd
description: Wire this repo to GitHub and a Snowflake account so an adopted agent ships through dev, test and prod. Creates the GitHub environments and variables, the OIDC users, approval gates, and creates the agent in each environment. Triggers - set up CI/CD, set up the pipeline, configure environments, wire GitHub to Snowflake, first deploy.
---

# Set up CI/CD for the adopted agent

Run after `adopt-agent`. Ask before each step that changes Snowflake or GitHub, and
show the command first. Never print tokens or PATs.

## Preconditions
- `agentops.yml` is filled in and `uv run ops generate` has run.
- `gh auth status` shows an account that can create environments on the repo.
- `snow` connection to the target Snowflake account with ACCOUNTADMIN for the
  one-time bootstrap only (CI uses least-privilege deployer roles).
- The repo is pushed to GitHub (private or public).

## Steps

1. **Repo identity.** Read the owner/repo and the numeric IDs the OIDC subject needs:
   ```bash
   gh repo view --json nameWithOwner,owner -q .nameWithOwner
   gh api repos/<owner>/<repo> --jq '[.owner.id, .id] | @tsv'
   gh api repos/<owner>/<repo>/actions/oidc/customization/sub
   ```
   The subject must include the numeric IDs
   (`repo:<owner>@<owner_id>/<repo>@<repo_id>:environment:<env>`) when the response
   says `use_immutable_subject` is true. If it does not, tell the user and adjust
   `bootstrap/setup.sql` to the plain `repo:<owner>/<repo>:environment:<env>` form.
   Write `github.repo` into `agentops.yml`.

2. **Bootstrap Snowflake (once).** Needs ACCOUNTADMIN:
   ```bash
   uv run snow sql -c <connection> -f bootstrap/setup.sql \
     -D github_owner=<owner> -D github_owner_id=<id> \
     -D github_repo_name=<repo> -D github_repo_id=<id> \
     -D dcm_database=<db> -D dcm_schema=<schema> -D warehouse=<wh>
   ```

3. **Data access for the deployers.** If the data databases already exist, run
   `aux/data/grant_deployers.sql` (see `docs/naming.md`). Without it the
   audience-role grants in DCM fail with "Insufficient privileges".

4. **GitHub environments and variables.** Create `dev`, `test`, `prod`:
   ```bash
   for e in dev test prod; do
     gh api -X PUT repos/<owner>/<repo>/environments/$e >/dev/null
     gh variable set SNOWFLAKE_ACCOUNT --env $e --body "<ORG-ACCOUNT>"
     gh variable set SNOWFLAKE_USER    --env $e --body "AGENTOPS_CI_${e^^}"
   done
   ```
   `SNOWFLAKE_ACCOUNT` is the account identifier written `ORG-ACCOUNT`.
   Restrict `test` and `prod` to the `main` branch, and add required reviewers
   (engineering for test, the business for prod) from `agentops.yml`:
   ```bash
   gh api -X PUT repos/<owner>/<repo>/environments/prod --input - <<'JSON'
   {"reviewers":[{"type":"Team","id":<team_id>}],
    "deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
   JSON
   ```
   Teams exist only for organisation repos. For a personal repo, use a `User` reviewer.
   Ask the user who approves which gate.

5. **Create the agent in each environment (once).** The first DCM deploy creates
   `AGENTS_<ENV>`; the agent must exist before the audience grants succeed. Order:
   - push to `main` and let `Main` run to the first failure, or run
     `snow dcm deploy` locally per environment;
   - then `uv run ops sql <ENV> bootstrap/agent.sql` for DEV, TEST, PROD;
   - re-run the failed `Main` job.

6. **Prove it.** Merge a one-line change to the agent instructions through a PR.
   Expect: PR plan comment, test deploy + evaluation report on the run page, prod
   waiting for approval. Approve prod. Then run the **Rollback** workflow with the
   previous release or commit and confirm the `PROD` alias moved back.

## Gotchas to handle, not to explain away
- Actions must be SHA-pinned and on the org allow-list; third-party actions may be
  blocked, which is why releases use `gh`.
- The spec stage must be `SNOWFLAKE_SSE` (already in the generated definitions).
- `CREATE AGENT` leaves a LIVE version that blocks `ADD VERSION`; `bootstrap/agent.sql`
  commits it. A Snowsight edit creates a new live version and the next release fails
  until it is committed or discarded.
- An unpinned default follows every new version, so bootstrap and promote pin it.
- `ADD AGENT` to CoWork fails if the agent is already listed, so it runs once.
