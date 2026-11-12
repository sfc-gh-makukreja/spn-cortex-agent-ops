-- ============================================================================
-- One-time bootstrap. Run by hand as ACCOUNTADMIN; CI never runs this file.
-- Safe to re-run.
--
--   snow sql -c <connection> -f bootstrap/setup.sql \
--     -D github_owner=<owner> -D github_owner_id=<id> \
--     -D github_repo_name=<repo> -D github_repo_id=<id> \
--     -D dcm_database=PLATFORM_CONTROL -D dcm_schema=PROJECTS \
--     -D warehouse=AGENTOPS_CI_WH
--
-- The setup-cicd skill fills these in. Creates only what CI cannot create for
-- itself: a CI warehouse, the DCM project home, one deployer role and one OIDC
-- service user per environment, and a network policy for GitHub Actions.
-- Everything else (AGENTS_<ENV> and what is inside) is created by the pipelines.
-- Your data databases (<NAME>_<ENV>) are yours: see docs/naming.md.
-- ============================================================================

USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS <% warehouse %>
    WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Runs agent CI/CD jobs';

-- A DCM project cannot create the database it lives in.
CREATE DATABASE IF NOT EXISTS <% dcm_database %>;
CREATE SCHEMA IF NOT EXISTS <% dcm_database %>.<% dcm_schema %>;

USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS AGENTOPS_DEPLOYER_DEV;
CREATE ROLE IF NOT EXISTS AGENTOPS_DEPLOYER_TEST;
CREATE ROLE IF NOT EXISTS AGENTOPS_DEPLOYER_PROD;

-- So SYSADMIN (and you) can see everything the pipelines create.
GRANT ROLE AGENTOPS_DEPLOYER_DEV  TO ROLE SYSADMIN;
GRANT ROLE AGENTOPS_DEPLOYER_TEST TO ROLE SYSADMIN;
GRANT ROLE AGENTOPS_DEPLOYER_PROD TO ROLE SYSADMIN;

-- WITH GRANT OPTION: DCM grants warehouse usage on to the audience roles it creates.
GRANT USAGE ON WAREHOUSE <% warehouse %> TO ROLE AGENTOPS_DEPLOYER_DEV  WITH GRANT OPTION;
GRANT USAGE ON WAREHOUSE <% warehouse %> TO ROLE AGENTOPS_DEPLOYER_TEST WITH GRANT OPTION;
GRANT USAGE ON WAREHOUSE <% warehouse %> TO ROLE AGENTOPS_DEPLOYER_PROD WITH GRANT OPTION;

GRANT USAGE ON DATABASE <% dcm_database %> TO ROLE AGENTOPS_DEPLOYER_DEV;
GRANT USAGE ON DATABASE <% dcm_database %> TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT USAGE ON DATABASE <% dcm_database %> TO ROLE AGENTOPS_DEPLOYER_PROD;

GRANT USAGE, CREATE DCM PROJECT ON SCHEMA <% dcm_database %>.<% dcm_schema %> TO ROLE AGENTOPS_DEPLOYER_DEV;
GRANT USAGE, CREATE DCM PROJECT ON SCHEMA <% dcm_database %>.<% dcm_schema %> TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT USAGE, CREATE DCM PROJECT ON SCHEMA <% dcm_database %>.<% dcm_schema %> TO ROLE AGENTOPS_DEPLOYER_PROD;

USE ROLE ACCOUNTADMIN;

-- Each deployer creates and owns its own AGENTS_<ENV> database.
GRANT CREATE DATABASE ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_DEV;
GRANT CREATE DATABASE ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT CREATE DATABASE ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_PROD;

-- DCM defines the audience roles in test and prod (generated access.sql).
GRANT CREATE ROLE ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT CREATE ROLE ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_PROD;

-- Agent evaluations run as a task; without this every evaluation fails.
GRANT EXECUTE TASK ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_DEV;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE AGENTOPS_DEPLOYER_PROD;

-- Cortex Search, Cortex Analyst, agents and the evaluation judge.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE AGENTOPS_DEPLOYER_DEV;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE AGENTOPS_DEPLOYER_TEST;
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE AGENTOPS_DEPLOYER_PROD;

-- Lets everyone open CoWork; which agents they see is down to their role.
GRANT USAGE ON SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT TO ROLE PUBLIC;

-- GitHub-hosted runners are usually not on an account network allowlist. This
-- user-level policy admits the CI users from GitHub Actions and nowhere else.
-- GITHUBACTIONS_GLOBAL is maintained by Snowflake as GitHub's ranges change.
USE ROLE SECURITYADMIN;
CREATE NETWORK POLICY IF NOT EXISTS AGENTOPS_CI_GITHUB_ONLY
    ALLOWED_NETWORK_RULE_LIST = ('SNOWFLAKE.NETWORK_SECURITY.GITHUBACTIONS_GLOBAL')
    COMMENT = 'Agent CI service users: GitHub Actions runners only';

/* Service users: GitHub OIDC, no stored secrets. Each user trusts exactly one
   GitHub Environment, so a job can only log in as AGENTOPS_CI_PROD if it runs in
   the repo's "prod" environment, which needs the business to approve.
   The subject uses GitHub's immutable form with numeric IDs; find them with
     gh api repos/<owner>/<repo> --jq '.owner.id, .id'
   and check the format with
     gh api repos/<owner>/<repo>/actions/oidc/customization/sub */
USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS AGENTOPS_CI_DEV TYPE = SERVICE
    WORKLOAD_IDENTITY = (TYPE = OIDC ISSUER = 'https://token.actions.githubusercontent.com'
        SUBJECT = 'repo:<% github_owner %>@<% github_owner_id %>/<% github_repo_name %>@<% github_repo_id %>:environment:dev')
    DEFAULT_ROLE = AGENTOPS_DEPLOYER_DEV DEFAULT_WAREHOUSE = <% warehouse %>
    COMMENT = 'GitHub Actions, dev environment';

CREATE USER IF NOT EXISTS AGENTOPS_CI_TEST TYPE = SERVICE
    WORKLOAD_IDENTITY = (TYPE = OIDC ISSUER = 'https://token.actions.githubusercontent.com'
        SUBJECT = 'repo:<% github_owner %>@<% github_owner_id %>/<% github_repo_name %>@<% github_repo_id %>:environment:test')
    DEFAULT_ROLE = AGENTOPS_DEPLOYER_TEST DEFAULT_WAREHOUSE = <% warehouse %>
    COMMENT = 'GitHub Actions, test environment';

CREATE USER IF NOT EXISTS AGENTOPS_CI_PROD TYPE = SERVICE
    WORKLOAD_IDENTITY = (TYPE = OIDC ISSUER = 'https://token.actions.githubusercontent.com'
        SUBJECT = 'repo:<% github_owner %>@<% github_owner_id %>/<% github_repo_name %>@<% github_repo_id %>:environment:prod')
    DEFAULT_ROLE = AGENTOPS_DEPLOYER_PROD DEFAULT_WAREHOUSE = <% warehouse %>
    COMMENT = 'GitHub Actions, prod environment';

USE ROLE SECURITYADMIN;

GRANT ROLE AGENTOPS_DEPLOYER_DEV  TO USER AGENTOPS_CI_DEV;
GRANT ROLE AGENTOPS_DEPLOYER_TEST TO USER AGENTOPS_CI_TEST;
GRANT ROLE AGENTOPS_DEPLOYER_PROD TO USER AGENTOPS_CI_PROD;

ALTER USER AGENTOPS_CI_DEV  SET NETWORK_POLICY = AGENTOPS_CI_GITHUB_ONLY;
ALTER USER AGENTOPS_CI_TEST SET NETWORK_POLICY = AGENTOPS_CI_GITHUB_ONLY;
ALTER USER AGENTOPS_CI_PROD SET NETWORK_POLICY = AGENTOPS_CI_GITHUB_ONLY;
