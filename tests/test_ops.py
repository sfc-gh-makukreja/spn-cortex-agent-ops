import yaml

from ops import cli

CFG = {
    "agent": {"name": "my_agent", "display_name": "My Agent", "comment": "x",
              "spec": "agent/agent.yaml", "semantic_views": []},
    "data_databases": ["SALES"],
    "audiences": {"TEST": "UAT_USER", "PROD": "PROD_USER"},
    "extra_grants": [],
    "snowflake": {"account": "ORG-ACC", "ci_warehouse": "AGENTOPS_CI_WH",
                  "dcm_database": "PLATFORM_CONTROL", "dcm_schema": "PROJECTS"},
}

SPEC = """\
tools:
  - tool_spec: {type: cortex_analyst_text_to_sql, name: Analyst}
  - tool_spec: {type: cortex_search, name: Search}
  - tool_spec: {type: generic, name: Recompute}
tool_resources:
  Analyst: {semantic_view: "DEMO_DB.CORE.ORDERS_SV"}
  Search: {search_service: DEMO_DB.CORE.DOCS_SEARCH}
  Recompute: {type: function, identifier: "DEMO_DB.CORE.RECOMPUTE(FLOAT)"}
"""

SV = """\
name: ORDERS_SV
tables:
  - name: orders
    base_table: {database: DEMO_DB, schema: CORE, table: ORDERS}
"""


def test_render_rewrites_dev_names_only_for_known_databases():
    text = "SALES_DEV.CORE.T AGENTS_DEV.CORE.A OTHER_DEV.X"
    assert cli.render_text(text, "PROD", CFG) == "SALES_PROD.CORE.T AGENTS_PROD.CORE.A OTHER_DEV.X"


def test_adopt_maps_names_and_flags_unconventional_databases(tmp_path):
    spec = tmp_path / "in.yaml"
    spec.write_text(SPEC)
    sv = tmp_path / "orders.sv.yaml"
    sv.write_text(SV)
    notes = cli.adopt(spec, tmp_path / "out", {"DEMO_DB": "SALES_DEV"}, [sv], CFG)
    assert not any(n.startswith("WARNING") for n in notes)
    # The semantic view is deployed to AGENTS_<ENV>.CONTEXT under the name in its YAML
    agent_yaml = (tmp_path / "out" / "agent.yaml").read_text()
    assert "AGENTS_DEV.CONTEXT.ORDERS_SV" in agent_yaml
    # the parsed value is exact: quoting must survive the rewrite
    adopted = yaml.safe_load(agent_yaml)
    assert adopted["tool_resources"]["Analyst"]["semantic_view"] == "AGENTS_DEV.CONTEXT.ORDERS_SV"
    assert "SALES_DEV.CORE.DOCS_SEARCH" in agent_yaml
    assert "SALES_DEV" in (tmp_path / "out" / "orders_sv.sv.yaml").read_text()

    notes = cli.adopt(spec, tmp_path / "out2", {}, [], CFG)
    assert any(n.startswith("WARNING") for n in notes)


def test_dependencies_found_in_tool_resources():
    deps = cli.spec_dependencies(yaml.safe_load(SPEC))
    assert deps["semantic_views"] == ["DEMO_DB.CORE.ORDERS_SV"]
    assert deps["search_services"] == ["DEMO_DB.CORE.DOCS_SEARCH"]
    assert deps["functions"] == ["DEMO_DB.CORE.RECOMPUTE(FLOAT)"]


def test_access_sql_grants_exactly_what_the_tools_touch():
    spec = yaml.safe_load(SPEC.replace("DEMO_DB", "SALES_DEV"))
    sv = yaml.safe_load(SV.replace("DEMO_DB", "SALES_DEV"))
    sql = cli.access_sql(CFG, spec, [sv])
    assert "DEFINE ROLE MY_AGENT_{{ env }}_USER" in sql
    assert "GRANT SELECT ON SEMANTIC VIEW SALES_{{ env }}.CORE.ORDERS_SV" in sql
    assert "GRANT USAGE ON CORTEX SEARCH SERVICE SALES_{{ env }}.CORE.DOCS_SEARCH" in sql
    assert "GRANT USAGE ON FUNCTION SALES_{{ env }}.CORE.RECOMPUTE(FLOAT)" in sql
    assert "GRANT SELECT ON TABLE SALES_{{ env }}.CORE.ORDERS" in sql
    assert "GRANT USAGE ON DATABASE SALES_{{ env }}" in sql


def test_tool_warehouse_is_granted_to_the_audience_role():
    spec = {"tool_resources": {"Analyst": {"semantic_view": "SALES_DEV.CORE.SV",
                                           "execution_environment": {"type": "warehouse", "warehouse": "TOOL_WH"}}}}
    assert cli.spec_dependencies(spec)["warehouses"] == ["TOOL_WH"]
    assert "GRANT USAGE ON WAREHOUSE TOOL_WH TO ROLE MY_AGENT_{{ env }}_USER" in cli.access_sql(CFG, spec, [])


def test_manifest_has_one_target_per_environment():
    doc = yaml.safe_load(cli.manifest_yaml(CFG))
    assert list(doc["targets"]) == ["DEV", "TEST", "PROD"]
    assert doc["targets"]["PROD"]["project_owner"] == "AGENTOPS_DEPLOYER_PROD"


def test_sql_args_pin_display_name_for_prod_only():
    test = cli.snow_sql_args(CFG, "TEST", "f.sql", ["-D", "x=1"])
    assert "display=My Agent (TEST)" in test and test[-2:] == ["-D", "x=1"]
    assert "display=My Agent" in cli.snow_sql_args(CFG, "PROD", "f.sql", [])
