-- Add a version to the agent from the spec uploaded for this commit. It is LAST
-- until promoted; the default (what CoWork uses) stays pinned.
--   uv run ops sql PROD ops/release.sql \
--     -D label=<sha> -D note='<sha7> · <subject> · <run url>' -D spec=/tmp/agent_spec.yaml

PUT 'file://<% spec %>' @AGENTS_<% env %>.CORE.AGENT_SPECS/<% label %>/
  AUTO_COMPRESS = FALSE OVERWRITE = TRUE;

ALTER AGENT AGENTS_<% env %>.CORE.<% agent %>
  ADD VERSION FROM @AGENTS_<% env %>.CORE.AGENT_SPECS/<% label %>/
  COMMENT = '<% note %>';
