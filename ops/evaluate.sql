-- Evaluate the version just released, before it is promoted. Fails only if the
-- run does not finish (or is cancelled); ops/eval_report.sql reports the scores.
-- PARTIALLY_COMPLETED counts as finished: the report shows what scored.
--   uv run ops sql TEST ops/evaluate.sql -D run=TEST-abc1234-1 -D config=/tmp/eval_config.yaml

USE SCHEMA AGENTS_<% env %>.CORE;   -- an evaluation runs in the session schema

PUT 'file://<% config %>' @AGENTS_<% env %>.CORE.EVAL_CONFIG/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE;

EXECUTE IMMEDIATE $$
DECLARE
  status STRING DEFAULT '';
  waited INTEGER DEFAULT 0;
  incomplete EXCEPTION (-20002, 'Evaluation <% run %> did not complete');
BEGIN
  CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', '<% run %>'),
    '@AGENTS_<% env %>.CORE.EVAL_CONFIG/eval_config.yaml');
  -- Wait for an end state, at most 15 minutes. Invocation completes before the
  -- metrics are computed.
  WHILE (COALESCE(status, '') NOT IN ('COMPLETED', 'PARTIALLY_COMPLETED', 'CANCELLED') AND waited < 900) DO
    SELECT SYSTEM$WAIT(5);
    waited := waited + 5;
    CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '<% run %>'),
      '@AGENTS_<% env %>.CORE.EVAL_CONFIG/eval_config.yaml');
    SELECT "STATUS" INTO :status FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  END WHILE;
  IF (status NOT IN ('COMPLETED', 'PARTIALLY_COMPLETED')) THEN
    RAISE incomplete;
  END IF;
  RETURN 'Evaluation <% run %> completed';
END;
$$;
