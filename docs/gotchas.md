# Gotchas

Hard-won lessons from running this flow.

- **Actions must be SHA-pinned and on the org allow-list**, including actions used
  inside composite actions. Third-party actions (for example `action-gh-release`) may
  not be allowed, so the workflows use `gh` for the release. Check
  `Settings > Actions` before the first run.
- **OIDC subject may need numeric IDs.** Some organisations use
  `repo:owner@OWNER_ID/repo@REPO_ID:environment:<env>`. Check with
  `gh api repos/<owner>/<repo>/actions/oidc/customization/sub`.
- **The agent spec stage must be `SNOWFLAKE_SSE`.** Otherwise `ADD VERSION FROM` cannot
  read the spec.
- **`CREATE AGENT` leaves a LIVE version, and `ADD VERSION` is refused while one
  exists.** `bootstrap/agent.sql` commits it. A Snowsight edit makes a new live version,
  and the next release fails until it is committed or discarded.
- **An unpinned default follows every new version** ("the latest committed version"), so
  a release would go live before promotion. Bootstrap and promote pin it to a
  `VERSION$N`; `DEFAULT_VERSION = LAST` floats too.
- **The first DCM deploy cannot create the audience grants** until the agent exists.
  Create the agent (`bootstrap/agent.sql`), then re-run the pipeline.
- **`ADD AGENT` to CoWork fails if the agent is already listed**, so it runs once, in
  `bootstrap/agent.sql`.
- **DCM does not define agents.** It owns the agent's home, roles and grants; the agent
  is versioned by the release SQL.
- **The DCM plan does not show grants on agents or Cortex Search services**, but deploys
  and manages them. Check with `SHOW GRANTS IN DCM PROJECT`.
- **User network policy overrides the account policy** for the CI users only, so
  GitHub-hosted runners can connect without opening the account policy to everyone.
- **Agent evaluations run as a task**, so the deployer roles need `EXECUTE TASK ON
  ACCOUNT`; without it every evaluation fails.
- **Do not run an evaluation in prod** if the agent writes data: it would write real rows.
  Evaluations run in TEST; prod ships the commit scored there.
