-- Let the pipeline's deployer roles manage grants on your data databases. DCM
-- (running as the deployer) grants the agent's audience roles SELECT/USAGE on the
-- objects the agent's tools read; it can only do that if it holds those privileges
-- WITH GRANT OPTION. Run as the owner of the databases (or ACCOUNTADMIN).
--   snow sql -c <connection> -f aux/data/grant_deployers.sql -D domain=SALES
--
-- This only grants rights to pass on. It does not let the deployers change your data.

EXECUTE IMMEDIATE $$
DECLARE
  envs ARRAY DEFAULT ['DEV', 'TEST', 'PROD'];
  e STRING;
BEGIN
  FOR i IN 0 TO ARRAY_SIZE(:envs) - 1 DO
    e := GET(:envs, :i)::STRING;
    EXECUTE IMMEDIATE 'GRANT USAGE ON DATABASE <% domain %>_' || e || ' TO ROLE AGENTOPS_DEPLOYER_' || e || ' WITH GRANT OPTION';
    EXECUTE IMMEDIATE 'GRANT USAGE ON ALL SCHEMAS IN DATABASE <% domain %>_' || e || ' TO ROLE AGENTOPS_DEPLOYER_' || e || ' WITH GRANT OPTION';
    EXECUTE IMMEDIATE 'GRANT SELECT ON ALL TABLES IN DATABASE <% domain %>_' || e || ' TO ROLE AGENTOPS_DEPLOYER_' || e || ' WITH GRANT OPTION';
    EXECUTE IMMEDIATE 'GRANT SELECT ON ALL VIEWS IN DATABASE <% domain %>_' || e || ' TO ROLE AGENTOPS_DEPLOYER_' || e || ' WITH GRANT OPTION';
    EXECUTE IMMEDIATE 'GRANT SELECT ON FUTURE TABLES IN DATABASE <% domain %>_' || e || ' TO ROLE AGENTOPS_DEPLOYER_' || e || ' WITH GRANT OPTION';
  END FOR;
  RETURN 'done';
END;
$$;

-- Not covered here (grant them yourself where the agent uses them):
--   GRANT USAGE ON CORTEX SEARCH SERVICE <db>.<schema>.<service> TO ROLE AGENTOPS_DEPLOYER_<ENV> WITH GRANT OPTION;
--   GRANT USAGE ON FUNCTION|PROCEDURE <db>.<schema>.<name>(<args>) TO ROLE AGENTOPS_DEPLOYER_<ENV> WITH GRANT OPTION;
-- Semantic views live in AGENTS_<ENV>.CONTEXT, which the deployer creates and owns.
