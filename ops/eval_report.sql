-- One evaluation run as markdown for the GitHub job summary: what the judges saw
-- the agent do, in their own words. There is no bar and no pass or fail. The agent
-- varies from run to run, so a score is a pointer to a behaviour, not a verdict;
-- the approver of the next environment reads the behaviour and decides.
--   uv run ops sql TEST ops/eval_report.sql -D run=TEST-abc1234-1 --format json
WITH scores AS (
    SELECT REPLACE(LEFT(INPUT, 90), '|', '/') AS question,
           METRIC_NAME AS metric,
           EVAL_AGG_SCORE AS score,
           METRIC_CALLS[0]:explanation::STRING AS reason   -- the judge's own words
      FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
             'AGENTS_<% env %>', 'CORE', '<% agent %>', 'CORTEX AGENT', '<% run %>'))
),
per_question AS (
    SELECT question,
           MAX(IFF(metric = 'answer_correctness', score, NULL)) AS correctness,
           MAX(IFF(metric = 'logical_consistency', score, NULL)) AS consistency
      FROM scores GROUP BY 1
),
marked_down AS (
    SELECT * FROM scores WHERE score < 1
)
SELECT
    '### Evaluation `<% run %>`\n\n'
      || (SELECT COUNT(*) FROM per_question) || ' questions, '
      || (SELECT COUNT(DISTINCT question) FROM marked_down)
      || ' with something a judge held back. Read what the agent did, not the numbers.'

      || COALESCE('\n\n**What the judges saw**\n\n' || (
           SELECT AI_AGG(question || ' (' || metric || '): ' || reason,
                         'These are LLM judges'' explanations of what an AI agent did on evaluation '
                         || 'questions. In two or three plain sentences for the business owner deciding '
                         || 'whether to release it, describe the agent''s behaviour: what it got wrong or '
                         || 'could not back with evidence. Do not quote scores. No headings.')
             FROM marked_down WHERE reason IS NOT NULL),
         '\n\nNo judge held anything back on this run.')

      || COALESCE('\n\n<details><summary>Each judge''s reasons</summary>\n\n' || (
           SELECT LISTAGG('- **' || question || '**, ' || metric || ': '
                            || COALESCE(REPLACE(reason, '\n', ' '), 'the judge gave no explanation'), '\n')
                    WITHIN GROUP (ORDER BY question, metric)
             FROM marked_down) || '\n\n</details>', '')

      || '\n\n<details><summary>Scores, as pointers</summary>\n\n'
      || '| Question | Answer correctness | Logical consistency |\n|---|---|---|\n'
      || (SELECT LISTAGG('| ' || question
                           || ' | ' || COALESCE(TO_VARCHAR(correctness, 'FM0.00'), '-')
                           || ' | ' || COALESCE(TO_VARCHAR(consistency, 'FM0.00'), '-') || ' |', '\n')
                    WITHIN GROUP (ORDER BY question)
            FROM per_question)
      || '\n\n</details>'

      || '\n\nTraces for each question: Snowsight, AI & ML, Agents, <% agent %> in AGENTS_<% env %>, Evaluations.'
      AS REPORT;
