-- Optional helper. Your data is out of scope for this repo; this script only
-- builds the per-environment copies the convention expects, from a DEV database
-- you already have. See docs/naming.md.
--
-- Replace the three values, then run as a role that owns the DEV database:
--   snow sql -c <connection> -f aux/data/clone_environments.sql \
--     -D domain=SALES -D with_data=false
--
-- <domain>_DEV is yours and must already exist. TEST and PROD are created as zero-copy
-- clones (with_data=true) or as empty structure-only copies (with_data=false).
-- Cortex Search services are NOT cloned this way: recreate them in each environment
-- (CREATE CORTEX SEARCH SERVICE <domain>_<ENV>.<schema>.<name> ...), then re-run.

CREATE DATABASE IF NOT EXISTS <% domain %>_TEST CLONE <% domain %>_DEV;
CREATE DATABASE IF NOT EXISTS <% domain %>_PROD CLONE <% domain %>_DEV;

-- with_data=false: keep the structure, drop the rows. Prefer this for PROD if
-- DEV holds synthetic or test data that should not ship.
EXECUTE IMMEDIATE $$
DECLARE
  c1 CURSOR FOR
    SELECT table_catalog, table_schema, table_name
      FROM IDENTIFIER('<% domain %>_PROD.INFORMATION_SCHEMA.TABLES')
     WHERE table_type = 'BASE TABLE' AND table_schema <> 'INFORMATION_SCHEMA';
BEGIN
  IF ('<% with_data %>' = 'false') THEN
    FOR rec IN c1 DO
      EXECUTE IMMEDIATE 'TRUNCATE TABLE ' || rec.table_catalog || '.' || rec.table_schema || '.' || rec.table_name;
    END FOR;
  END IF;
  RETURN 'done';
END;
$$;
