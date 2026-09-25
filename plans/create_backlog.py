#!/usr/bin/env python3
"""Create the GitHub issues and project items described in plans/backlog.py.

Recipe (idempotent, resumable):
    gh auth status            # the personal account must be active, scope 'project'
    python3 plans/create_backlog.py

What it does, for each backlog entry in order:
  1. creates the issue with labels level:*, area:*, priority:* and a body that
     already lists its blockers (issue numbers are predicted: the repository has
     no other issues, and each creation is checked against the prediction);
  2. links it as a sub-issue of its parent (epic > story > task/experiment);
  3. records "blocked by" dependencies through the issue dependencies API;
  4. adds it to the project and sets Status, Level and Priority;
  5. closes it if the entry is marked closed.

On reruns it also reconciles: titles and bodies changed in backlog.py are pushed,
dependencies removed from backlog.py are deleted, closed entries are closed with
their reason, and project fields follow the entries.

State is kept in plans/backlog-issues.json (key -> number, id, node_id, item id),
so a rerun skips what exists. Content-creating calls are spaced to stay under
GitHub's secondary rate limits.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backlog import BACKLOG  # noqa: E402

OWNER, REPO, PROJECT_NUMBER = "FrancescoPolitano", "swingtag", 1
STATE = Path(__file__).parent / "backlog-issues.json"
PAUSE = 1.0  # seconds between content-creating calls

LABELS = {
    "level:epic": "5319e7", "level:story": "1d76db", "level:task": "0e8a16",
    "level:experiment": "fbca04",
    "priority:must": "b60205", "priority:should": "d93f0b", "priority:could": "c5def5",
    **{f"area:{a}": "ededed" for a in
       ("core", "theme", "publisher", "infra", "examples", "tooling", "docs", "process")},
}


def gh(*args: str, input_json: dict | None = None) -> dict | list | str:
    cmd = ["gh", *args]
    if input_json is not None:
        cmd += ["--input", "-"]
    out = subprocess.run(cmd, input=json.dumps(input_json) if input_json is not None else None,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}: {out.stderr.strip()}")
    try:
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except json.JSONDecodeError:
        return out.stdout


def graphql(query: str, **variables) -> dict:
    return gh("api", "graphql", input_json={"query": query, "variables": variables})["data"]


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


def body_for(entry: dict, numbers: dict[str, int], titles: dict[str, str]) -> str:
    lines = [f"**Level:** {entry['level'].capitalize()} · **Area:** {entry['area']} · "
             f"**Priority:** {entry['priority'].capitalize()}"]
    if entry["spec"]:
        lines.append(f"**Spec:** {entry['spec']}")
    if entry["what"]:
        lines += ["", entry["what"]]
    if entry["done"]:
        mark = "x" if entry["closed"] else " "
        lines += ["", "### Done when"] + [f"- [{mark}] {d}" for d in entry["done"]]
    if entry["deps"]:
        lines += ["", "### Blocked by"] + [f"- #{numbers[d]} {titles[d]}" for d in entry["deps"]]
    lines += ["", f"<sub>backlog key: `{entry['key']}` · source: plans/backlog.py</sub>"]
    return "\n".join(lines)


def ensure_labels() -> None:
    existing = {l["name"] for l in gh("api", f"repos/{OWNER}/{REPO}/labels", "--paginate")}
    for name, color in LABELS.items():
        if name not in existing:
            gh("api", f"repos/{OWNER}/{REPO}/labels", "-f", f"name={name}", "-f", f"color={color}")


def project_meta() -> tuple[str, dict[str, str], dict[str, dict[str, str]]]:
    data = graphql("""query($o:String!,$n:Int!){user(login:$o){projectV2(number:$n){id
        fields(first:50){nodes{... on ProjectV2SingleSelectField{id name options{id name}}}}}}}""",
                   o=OWNER, n=PROJECT_NUMBER)["user"]["projectV2"]
    fields, options = {}, {}
    for f in data["fields"]["nodes"]:
        if f and "options" in f:
            fields[f["name"]] = f["id"]
            options[f["name"]] = {o["name"]: o["id"] for o in f["options"]}
    return data["id"], fields, options


def check_acyclic() -> None:
    deps = {e["key"]: e["deps"] for e in BACKLOG}
    seen, stack = set(), set()

    def visit(k):
        if k in stack:
            raise SystemExit(f"dependency cycle through {k}")
        if k not in seen:
            stack.add(k)
            for d in deps[k]:
                visit(d)
            stack.discard(k)
            seen.add(k)

    for k in deps:
        visit(k)


def main() -> None:
    check_acyclic()
    state = load_state()
    ensure_labels()
    project_id, fields, options = project_meta()

    existing_issues = gh("api", f"repos/{OWNER}/{REPO}/issues?state=all&per_page=1")
    first_free = (existing_issues[0]["number"] + 1) if existing_issues else 1
    base = min([v["number"] for v in state.values()] or [first_free])
    numbers = {e["key"]: base + i for i, e in enumerate(BACKLOG)}
    titles = {e["key"]: e["title"] for e in BACKLOG}
    by_key = {e["key"]: e for e in BACKLOG}

    # 1. issues
    for e in BACKLOG:
        if e["key"] in state:
            continue
        labels = [f"level:{e['level']}", f"area:{e['area']}", f"priority:{e['priority']}"]
        created = gh("api", f"repos/{OWNER}/{REPO}/issues", input_json={
            "title": e["title"], "body": body_for(e, numbers, titles), "labels": labels})
        if created["number"] != numbers[e["key"]]:
            raise SystemExit(f"number drift at {e['key']}: got #{created['number']}, "
                             f"expected #{numbers[e['key']]}; fix plans/backlog-issues.json")
        state[e["key"]] = {"number": created["number"], "id": created["id"],
                           "node_id": created["node_id"]}
        save_state(state)
        print(f"#{created['number']:>3} {e['level']:<10} {e['title']}", flush=True)
        time.sleep(PAUSE)

    # 2. sub-issues
    for e in BACKLOG:
        s = state[e["key"]]
        if e["parent"] and not s.get("linked"):
            parent = state[e["parent"]]["number"]
            gh("api", f"repos/{OWNER}/{REPO}/issues/{parent}/sub_issues", "-X", "POST",
               "-F", f"sub_issue_id={s['id']}")
            s["linked"] = True
            save_state(state)
            time.sleep(PAUSE)
    print("sub-issues linked", flush=True)

    # 2b. titles and bodies follow backlog.py
    for e in BACKLOG:
        s = state[e["key"]]
        body = body_for(e, numbers, titles)
        digest = hashlib.sha256((e["title"] + "\0" + body).encode()).hexdigest()
        if s.get("body_hash") != digest:
            gh("api", f"repos/{OWNER}/{REPO}/issues/{s['number']}", "-X", "PATCH",
               input_json={"title": e["title"], "body": body})
            s["body_hash"] = digest
            save_state(state)
            time.sleep(PAUSE)
    print("titles and bodies reconciled", flush=True)

    # 3. dependencies
    for e in BACKLOG:
        s = state[e["key"]]
        done = set(s.get("deps_done", []))
        for d in sorted(done - set(e["deps"])):
            gh("api", f"repos/{OWNER}/{REPO}/issues/{s['number']}/dependencies/blocked_by/"
               f"{state[d]['id']}", "-X", "DELETE")
            done.discard(d)
            s["deps_done"] = sorted(done)
            save_state(state)
            time.sleep(PAUSE)
        for d in e["deps"]:
            if d in done:
                continue
            try:
                gh("api", f"repos/{OWNER}/{REPO}/issues/{s['number']}/dependencies/blocked_by",
                   "-X", "POST", "-F", f"issue_id={state[d]['id']}")
            except RuntimeError as exc:
                print(f"dependency {e['key']} <- {d} not recorded: {exc}", flush=True)
                continue
            done.add(d)
            s["deps_done"] = sorted(done)
            save_state(state)
            time.sleep(PAUSE)
    print("dependencies recorded", flush=True)

    # 4. project items and fields
    for e in BACKLOG:
        s = state[e["key"]]
        if not s.get("item"):
            s["item"] = graphql("""mutation($p:ID!,$c:ID!){addProjectV2ItemById(
                input:{projectId:$p,contentId:$c}){item{id}}}""",
                                p=project_id, c=s["node_id"])["addProjectV2ItemById"]["item"]["id"]
            save_state(state)
        open_deps = [d for d in e["deps"] if not by_key[d]["closed"]]
        status = ("Done" if e["closed"] else e["status"] if e.get("status") else
                  "Ready" if e["level"] in ("task", "experiment") and not open_deps else "Backlog")
        values = {"Status": status, "Level": e["level"].capitalize(),
                  "Priority": e["priority"].capitalize()}
        if s.get("fields") != values:
            for field, value in values.items():
                graphql("""mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(
                    input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){
                    projectV2Item{id}}}""",
                        p=project_id, i=s["item"], f=fields[field], o=options[field][value])
            s["fields"] = values
            save_state(state)
    print("project items set", flush=True)

    # 5. close finished entries
    for e in BACKLOG:
        s = state[e["key"]]
        if e["closed"] and not s.get("closed"):
            gh("api", f"repos/{OWNER}/{REPO}/issues/{s['number']}", "-X", "PATCH",
               "-f", "state=closed", "-f", f"state_reason={e['reason']}")
            s["closed"] = True
            save_state(state)
            time.sleep(PAUSE)
    print(f"done: {len(state)} issues", flush=True)


if __name__ == "__main__":
    main()
