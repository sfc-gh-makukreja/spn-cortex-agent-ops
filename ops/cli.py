"""`ops <command>`: the agent ops commands CI and people both run.

Every environment is derived from one convention: specs and semantic views are
written with DEV names, and `render` rewrites them for TEST or PROD.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENVS = ("DEV", "TEST", "PROD")


def load_config(path: Path = ROOT / "agentops.yml") -> dict:
    return yaml.safe_load(path.read_text())


def home_databases(cfg: dict) -> list[str]:
    """Databases whose _DEV suffix is rewritten per environment."""
    return ["AGENTS", *[d.upper() for d in cfg.get("data_databases", [])]]


def render_text(text: str, env: str, cfg: dict) -> str:
    """Rewrite <DB>_DEV to <DB>_<env> for the agent home and the data databases."""
    for db in home_databases(cfg):
        text = re.sub(rf"\b{re.escape(db)}_DEV\b", f"{db}_{env}", text)
    return text


def render(path: Path, env: str, cfg: dict) -> str:
    text = render_text(path.read_text(), env, cfg)
    yaml.safe_load(text)  # fail loudly if the result is not valid YAML
    return text


def semantic_view_sql(path: Path, env: str, cfg: dict, check: bool) -> str:
    """SQL that validates (check) or creates/alters a semantic view in AGENTS_<env>.CONTEXT."""
    body = render(path, env, cfg)
    if "$$" in body:
        raise ValueError(f"{path} contains $$, which would end the SQL literal")
    return (f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('AGENTS_{env}.CONTEXT', "
            f"$${body}$$, {'TRUE' if check else 'FALSE'}, TRUE);\n")


def parse_fqn(value: str) -> tuple[str, str, str]:
    parts = [p.strip('"') for p in value.split(".")]
    if len(parts) != 3:
        raise ValueError(f"Expected DATABASE.SCHEMA.NAME, got {value!r}")
    return parts[0], parts[1], parts[2]


def spec_dependencies(spec: dict) -> dict:
    """What the agent's tools touch, read from tool_resources in the spec."""
    deps = {"semantic_views": [], "search_services": [], "functions": [], "procedures": [],
            "warehouses": []}
    for res in (spec.get("tool_resources") or {}).values():
        if not isinstance(res, dict):
            continue
        env_ = res.get("execution_environment") or {}
        if env_.get("warehouse"):
            deps["warehouses"].append(env_["warehouse"])
        if res.get("semantic_view"):
            deps["semantic_views"].append(res["semantic_view"])
        if res.get("search_service"):
            deps["search_services"].append(res["search_service"])
        ident = res.get("identifier")
        if ident:
            kind = str(res.get("type", "function")).lower()
            deps["procedures" if kind == "procedure" else "functions"].append(ident)
    return {k: sorted(set(v)) for k, v in deps.items()}


def semantic_view_tables(sv: dict) -> list[tuple[str, str, str]]:
    out = []
    for t in sv.get("tables", []) or []:
        bt = t.get("base_table") or {}
        if bt.get("database") and bt.get("schema") and bt.get("table"):
            out.append((bt["database"], bt["schema"], bt["table"]))
    return out


def adopt(spec_path: Path, out_dir: Path, mappings: dict[str, str], sv_paths: list[Path],
          cfg: dict) -> list[str]:
    """Normalise an exported agent (and semantic views) to DEV names and write them to the repo."""
    def remap(text: str) -> str:
        for old, new in mappings.items():
            text = re.sub(rf"\b{re.escape(old)}\b", new, text, flags=re.IGNORECASE)
        return text

    out_dir.mkdir(parents=True, exist_ok=True)
    notes = []
    spec_text = remap(spec_path.read_text())

    # Semantic views are deployed by the pipeline to AGENTS_<ENV>.CONTEXT under the
    # name inside the YAML, so the spec must point there and the file take that name.
    for sv_path in sv_paths:
        sv_text = remap(sv_path.read_text())
        sv_name = str(yaml.safe_load(sv_text)["name"])
        target = out_dir / f"{sv_name.lower()}.sv.yaml"
        target.write_text(sv_text)
        notes.append(f"wrote {target}")
        spec_text = re.sub(rf"\b[\w$]+\.[\w$]+\.{re.escape(sv_name)}\b",
                           f"AGENTS_DEV.CONTEXT.{sv_name}", spec_text, flags=re.IGNORECASE)

    spec = yaml.safe_load(spec_text)
    (out_dir / "agent.yaml").write_text(spec_text)
    notes.append(f"wrote {out_dir / 'agent.yaml'}")

    data_dev = {f"{d.upper()}_DEV" for d in cfg.get("data_databases", [])} | {"AGENTS_DEV"}
    deps = spec_dependencies(spec)
    for fqn in [f for k, v in deps.items() if k != "warehouses" for f in v]:
        db = parse_fqn(fqn.split("(")[0])[0]
        if db.upper() not in data_dev:
            notes.append(f"WARNING {fqn}: database {db} does not follow <NAME>_DEV; "
                         "add --map OLD=NEW or a data_databases entry in agentops.yml")
    return notes


def tmpl(fqn: str, cfg: dict) -> str:
    """Turn <DB>_DEV into <DB>_{{ env }} for templated DCM definitions."""
    for db in home_databases(cfg):
        fqn = re.sub(rf"\b{re.escape(db)}_DEV\b", db + "_{{ env }}", fqn, flags=re.IGNORECASE)
    return fqn


def access_sql(cfg: dict, spec: dict, sv_docs: list[dict]) -> str:
    """The DCM definition of each audience role and exactly the grants the agent's tools need."""
    agent = cfg["agent"]["name"].upper()
    wh = cfg["snowflake"]["ci_warehouse"]
    deps = spec_dependencies(spec)
    r = f"{agent}_{{{{ env }}}}_USER"
    lines = [
        "-- Generated by `ops generate`. One role per audience per environment, holding",
        "-- exactly what the agent's tools touch. DEV has no audience: engineers work as themselves.",
        "",
        "{% set audience = " + repr(dict(cfg.get("audiences") or {})) + " %}",
        "{% if env in audience %}",
        "",
        f"DEFINE ROLE {r}",
        f"    COMMENT = 'Uses the {{{{ env }}}} {agent} agent in CoWork';",
        f"GRANT ROLE {r} TO USER {{{{ audience[env] }}}};",
        "",
        f"GRANT USAGE ON WAREHOUSE {wh} TO ROLE {r};",
        f"GRANT USAGE ON DATABASE AGENTS_{{{{ env }}}} TO ROLE {r};",
    ]
    for s in ("CORE", "CONTEXT", "TOOLS"):
        lines.append(f"GRANT USAGE ON SCHEMA AGENTS_{{{{ env }}}}.{s} TO ROLE {r};")
    lines.append(f"GRANT USAGE ON AGENT AGENTS_{{{{ env }}}}.CORE.{agent} TO ROLE {r};")

    seen_schema, seen_db = set(), set()

    def grant_container(fqn: str):
        db, schema, _ = parse_fqn(fqn)
        if db.upper() == "AGENTS_DEV":
            return
        if db not in seen_db:
            seen_db.add(db)
            lines.append(f"GRANT USAGE ON DATABASE {tmpl(db, cfg)} TO ROLE {r};")
        if (db, schema) not in seen_schema:
            seen_schema.add((db, schema))
            lines.append(f"GRANT USAGE ON SCHEMA {tmpl(db + '.' + schema, cfg)} TO ROLE {r};")

    lines += ["", "-- The agent's tools"]
    for wh_name in deps["warehouses"]:
        if wh_name.upper() != wh.upper():
            lines.append(f"GRANT USAGE ON WAREHOUSE {wh_name} TO ROLE {r};")
    for fqn in deps["semantic_views"]:
        grant_container(fqn)
        lines.append(f"GRANT SELECT ON SEMANTIC VIEW {tmpl(fqn, cfg)} TO ROLE {r};")
    for fqn in deps["search_services"]:
        grant_container(fqn)
        lines.append(f"GRANT USAGE ON CORTEX SEARCH SERVICE {tmpl(fqn, cfg)} TO ROLE {r};")
    for fqn in deps["functions"]:
        grant_container(fqn.split("(")[0])
        lines.append(f"GRANT USAGE ON FUNCTION {tmpl(fqn, cfg)} TO ROLE {r};")
    for fqn in deps["procedures"]:
        grant_container(fqn.split("(")[0])
        lines.append(f"GRANT USAGE ON PROCEDURE {tmpl(fqn, cfg)} TO ROLE {r};")

    lines += ["", "-- The data behind the semantic views (their base tables)"]
    for sv in sv_docs:
        for db, schema, table in semantic_view_tables(sv):
            fqn = f"{db}.{schema}.{table}"
            grant_container(fqn)
            lines.append(f"GRANT SELECT ON TABLE {tmpl(fqn, cfg)} TO ROLE {r};")
    for extra in cfg.get("extra_grants") or []:
        lines.append(extra.replace("{env}", "{{ env }}").replace("{role}", r))
    lines += ["", "{% endif %}", ""]
    return "\n".join(lines)


PLATFORM_SQL = """-- Generated by `ops generate`. AGENTS_<ENV> is everything the agent team
-- changes. The agent itself is versioned outside DCM (DCM has no DEFINE AGENT);
-- DCM owns its home.

DEFINE DATABASE AGENTS_{{ env }};

DEFINE SCHEMA AGENTS_{{ env }}.CONTEXT;
DEFINE SCHEMA AGENTS_{{ env }}.TOOLS;
DEFINE SCHEMA AGENTS_{{ env }}.CORE;

-- Must be SNOWFLAKE_SSE or CREATE/ALTER AGENT cannot read the spec from it.
DEFINE STAGE AGENTS_{{ env }}.CORE.AGENT_SPECS
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Agent specs uploaded by CI, one folder per commit';

-- Without this file format Snowflake reads the evaluation YAML as CSV.
DEFINE FILE FORMAT AGENTS_{{ env }}.CORE.YAML_FILE_FORMAT
    TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = '\\n' SKIP_HEADER = 0
    FIELD_OPTIONALLY_ENCLOSED_BY = NONE ESCAPE_UNENCLOSED_FIELD = NONE;

DEFINE STAGE AGENTS_{{ env }}.CORE.EVAL_CONFIG
    FILE_FORMAT = AGENTS_{{ env }}.CORE.YAML_FILE_FORMAT
    COMMENT = 'Agent evaluation configs, uploaded by CI';
"""


def manifest_yaml(cfg: dict) -> str:
    sf = cfg["snowflake"]
    targets = {
        env: {
            "account_identifier": sf["account"],
            "project_name": f"{sf['dcm_database']}.{sf['dcm_schema']}.AGENTOPS_{env}",
            "project_owner": f"AGENTOPS_DEPLOYER_{env}",
            "templating_config": env,
        }
        for env in ENVS
    }
    doc = {
        "manifest_version": 2,
        "type": "DCM_PROJECT",
        "default_target": "DEV",
        "targets": targets,
        "templating": {"configurations": {e: {"env": e} for e in ENVS}},
    }
    header = ("# Generated by `ops generate` from agentops.yml. One DCM project per\n"
              "# environment, each owned by that environment's deployer role.\n")
    return header + yaml.safe_dump(doc, sort_keys=False)


def generate(cfg: dict) -> list[str]:
    spec = yaml.safe_load((ROOT / cfg["agent"]["spec"]).read_text())
    sv_docs = [yaml.safe_load((ROOT / p).read_text()) for p in cfg["agent"].get("semantic_views", [])]
    defs = ROOT / "dcm" / "sources" / "definitions"
    (defs / "platform").mkdir(parents=True, exist_ok=True)
    (defs / "access").mkdir(parents=True, exist_ok=True)
    (ROOT / "dcm" / "manifest.yml").write_text(manifest_yaml(cfg))
    (defs / "platform" / "agent_home.sql").write_text(PLATFORM_SQL)
    (defs / "access" / "access.sql").write_text(access_sql(cfg, spec, sv_docs))
    return ["dcm/manifest.yml", "dcm/sources/definitions/platform/agent_home.sql",
            "dcm/sources/definitions/access/access.sql"]


def sql_vars(cfg: dict, env: str) -> dict:
    """-D variables for snow sql, so the SQL files stay generic."""
    agent = cfg["agent"]
    display = agent["display_name"] if env == "PROD" else f"{agent['display_name']} ({env})"
    return {
        "env": env,
        "agent": agent["name"].upper(),
        "display": display,
        "comment": agent.get("comment", "").replace("'", ""),
        "warehouse": cfg["snowflake"]["ci_warehouse"],
    }


def snow_sql_args(cfg: dict, env: str, file: str, extra: list[str]) -> list[str]:
    """The argv for `snow sql -f FILE` with the agent variables and any extra -D k=v."""
    args = ["snow", "sql", "-x", "-f", file]
    for k, v in sql_vars(cfg, env).items():
        args += ["-D", f"{k}={v}"]
    return args + extra


def eval_dataset_sql(cfg: dict, env: str, questions: list[dict]) -> str:
    """Publish the business-owned questions as the table the evaluation reads."""
    agent = cfg["agent"]["name"].upper()
    table = f"AGENTS_{env}.CORE.{agent}_TEST_QUESTIONS"
    rows = []
    for q in questions:
        a = q["question"].replace("'", "''")
        g = q["good_answer"].replace("'", "''")
        rows.append(f"    ('{a}',\n     '{g}')")
    return (f"CREATE OR REPLACE TABLE {table} (INPUT_QUERY VARCHAR, GROUND_TRUTH VARIANT);\n"
            f"INSERT INTO {table} (INPUT_QUERY, GROUND_TRUTH)\n"
            "SELECT question, TO_VARIANT(OBJECT_CONSTRUCT('ground_truth_output', good_answer))\n"
            "FROM VALUES\n" + ",\n".join(rows) + "\nAS t(question, good_answer);\n")


def eval_config_yaml(cfg: dict) -> str:
    agent = cfg["agent"]["name"].upper()
    doc = {
        "evaluation": {
            "agent_params": {"agent_name": agent, "agent_type": "CORTEX AGENT",
                             "agent_version": "LAST"},
            "source_metadata": {"type": "dataset", "dataset_name": f"{agent}_TEST_QUESTIONS"},
        },
        "metrics": [{"name": "answer_correctness", "version": "v3"},
                    {"name": "logical_consistency", "version": "v3"}],
    }
    return "# Generated by `ops eval-config`.\n" + yaml.safe_dump(doc, sort_keys=False)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ops")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("render", help="render an agent spec or semantic view for one environment")
    s.add_argument("path", type=Path)
    s.add_argument("env", type=str.upper)

    s = sub.add_parser("semantic-view", help="SQL that creates a semantic view in one environment")
    s.add_argument("path", type=Path)
    s.add_argument("env", type=str.upper)
    s.add_argument("--check", action="store_true", help="validate only; create nothing")

    s = sub.add_parser("adopt", help="normalise an exported agent to DEV names and write it to agent/")
    s.add_argument("spec", type=Path, help="agent spec YAML, e.g. from `cortex agent-studio agent-read`")
    s.add_argument("--semantic-view", type=Path, action="append", default=[], dest="svs")
    s.add_argument("--map", action="append", default=[], metavar="OLD=NEW",
                   help="rename a database/schema token, e.g. DEMO_DB=LENDING_DEV (repeatable)")
    s.add_argument("--out", type=Path, default=ROOT / "agent")

    sub.add_parser("deps", help="list what the adopted agent's tools touch")
    sub.add_parser("semantic-views", help="paths of the semantic view files in agentops.yml")
    sub.add_parser("generate", help="generate the DCM manifest, agent home and audience grants")

    s = sub.add_parser("sql", help="run a SQL file with snow sql and the agent variables for one environment")
    s.add_argument("env", type=str.upper)
    s.add_argument("file")
    s.add_argument("extra", nargs=argparse.REMAINDER, help="more snow sql arguments, e.g. -D k=v")

    s = sub.add_parser("eval-dataset", help="SQL that publishes evals/questions.yml")
    s.add_argument("env", type=str.upper)
    sub.add_parser("eval-config", help="the evaluation config YAML")

    args = p.parse_args(argv)
    cfg = load_config()

    if args.cmd == "render":
        sys.stdout.write(render(args.path, args.env, cfg))
    elif args.cmd == "semantic-view":
        sys.stdout.write(semantic_view_sql(args.path, args.env, cfg, args.check))
    elif args.cmd == "adopt":
        maps = dict(m.split("=", 1) for m in args.map)
        for note in adopt(args.spec, args.out, maps, args.svs, cfg):
            print(note)
    elif args.cmd == "deps":
        spec = yaml.safe_load((ROOT / cfg["agent"]["spec"]).read_text())
        print(yaml.safe_dump(spec_dependencies(spec), sort_keys=False))
    elif args.cmd == "semantic-views":
        print("\n".join(cfg["agent"].get("semantic_views", [])))
    elif args.cmd == "generate":
        for f in generate(cfg):
            print("wrote", f)
    elif args.cmd == "sql":
        return subprocess.call(snow_sql_args(cfg, args.env, args.file, args.extra))
    elif args.cmd == "eval-dataset":
        qs = yaml.safe_load((ROOT / "evals" / "questions.yml").read_text())["questions"]
        sys.stdout.write(eval_dataset_sql(cfg, args.env, qs))
    elif args.cmd == "eval-config":
        sys.stdout.write(eval_config_yaml(cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
