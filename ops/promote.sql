-- Make a commit's newest version PROD and the default (what CoWork uses).
-- Rollback is the same call with an older commit.
--   uv run ops sql PROD ops/promote.sql -D commit=a1b2c3d

EXECUTE IMMEDIATE $$
DECLARE
  version STRING;
  not_deployed EXCEPTION (-20001, 'No version of AGENTS_<% env %>.CORE.<% agent %> is commit <% commit %>');
BEGIN
  SHOW VERSIONS IN AGENT AGENTS_<% env %>.CORE.<% agent %>;
  SELECT MAX_BY("name", "created_on") INTO :version
    FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
    WHERE STARTSWITH("comment", '<% commit %>');
  IF (version IS NULL) THEN
    RAISE not_deployed;
  END IF;

  EXECUTE IMMEDIATE 'ALTER AGENT AGENTS_<% env %>.CORE.<% agent %> MODIFY VERSION ' || version || ' SET ALIAS = PROD';
  -- Pinned explicitly: an unpinned default follows every new version.
  EXECUTE IMMEDIATE 'ALTER AGENT AGENTS_<% env %>.CORE.<% agent %> SET DEFAULT_VERSION = ''' || version || '''';
  RETURN 'Alias PROD on AGENTS_<% env %>.CORE.<% agent %> set to commit <% commit %> (' || version || '), also the default';
END;
$$;
