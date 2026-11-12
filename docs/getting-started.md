# Prerequisites

| You need | Why |
|---|---|
| A Snowflake account and a role that can use `ACCOUNTADMIN` once | One-time bootstrap of deployer roles, CI users and the network policy |
| An agent that already works | This repo adopts it; it does not build it. Build one with Snowsight, the `agent-studio` skill or [spn-demo-creator](https://github.com/sfc-gh-makukreja/spn-demo-creator) |
| Data in `<NAME>_DEV` (and TEST, PROD) | See the [naming convention](naming.md) |
| A GitHub repo (fork or use this template) | Environments, approvals and Actions |
| `gh`, `uv` and the Snowflake CLI (`snow`) | The skills and `ops` use them |
| Cortex Code (recommended) | The `adopt-agent` and `setup-cicd` skills guide each step and ask before changing anything |

## Check your GitHub organisation

Two things differ between organisations and break first deployments:

- **Actions allow-list.** Actions must be pinned to a commit SHA and, in some
  organisations, on an allow-list. The workflows use only `actions/checkout` and
  `astral-sh/setup-uv`, pinned. Third-party actions are avoided on purpose.
- **OIDC subject format.** Some organisations use GitHub's immutable subject with
  numeric IDs (`repo:owner@ID/repo@ID:environment:prod`). Check with
  `gh api repos/<owner>/<repo>/actions/oidc/customization/sub`; the `setup-cicd`
  skill does this for you.
