#!/usr/bin/env python3
"""Self-test for the starter-kit hooks: pipes sample hook JSON into each script
and checks the decision it prints. Builds throwaway git repos in a temp dir.

Run from anywhere:  python3 .claude/hooks/tests/run_hook_tests.py
Stdlib only. Exit code 0 when every case passes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_GUARD = os.path.join(HOOKS, "test_guard.py")
PROD_GUARD = os.path.join(HOOKS, "prod_boundary_guard.py")
STOP_GATE = os.path.join(HOOKS, "stop_verify_gate.py")

results = []


def run_hook(script, payload, project, extra_env=None, raw=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
    env.update(extra_env or {})
    data = raw if raw is not None else json.dumps(payload)
    proc = subprocess.run([sys.executable, script], input=data, capture_output=True, text=True,
                          env=env, cwd=project, timeout=60)
    out = proc.stdout.strip()
    parsed = json.loads(out) if out else None
    return proc.returncode, parsed, proc.stderr


def decision_of(parsed):
    if not parsed:
        return "pass"
    if "hookSpecificOutput" in parsed:
        return parsed["hookSpecificOutput"]["permissionDecision"]
    if parsed.get("decision") == "block":
        return "block"
    if "systemMessage" in parsed:
        return "warn"
    return "other"


def check(name, script, payload, expected, project, extra_env=None, raw=None):
    code, parsed, err = run_hook(script, payload, project, extra_env, raw)
    got = decision_of(parsed)
    ok = code == 0 and got == expected
    results.append(ok)
    print("{} {:<64} expected={:<5} got={}".format("PASS" if ok else "FAIL", name[:64], expected, got))
    if not ok:
        print("     stdout:", json.dumps(parsed)[:400], "\n     stderr:", err[:400])
    return parsed


def sh(cwd, *cmd):
    subprocess.run(list(cmd), cwd=cwd, check=True, capture_output=True)


def make_repo(root, branch="main"):
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    os.makedirs(os.path.join(root, "tests", "regression"), exist_ok=True)
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    os.makedirs(os.path.join(root, "spec", "models"), exist_ok=True)
    files = {
        ".claude/frozen-tests.txt": "# frozen tests\ntests/test_refund_rounding.py\ntests/regression/\nspec/**/*_frozen_spec.rb\n",
        "tests/test_refund_rounding.py": "def test_refund_rounds_half_up():\n    assert refund(999, 15) == 150\n",
        "tests/regression/test_inc_031.py": "def test_inc_031():\n    assert True\n",
        "tests/test_cart.py": "import pytest\n\ndef test_total():\n    assert 1 + 1 == 2\n\ndef test_empty():\n    assert [] == []\n",
        "spec/models/order_frozen_spec.rb": "describe Order do\n  it 'totals' do\n  end\nend\n",
        "src/pricing.py": "def refund(price, pct):\n    return int(price * pct / 100)\n",
        "pytest.ini": "[pytest]\naddopts = -q\n",
    }
    for rel, text in files.items():
        with open(os.path.join(root, rel), "w") as fh:
            fh.write(text)
    sh(root, "git", "init", "-q", "-b", branch)
    sh(root, "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
    sh(root, "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init")


def pre(tool, tool_input, project):
    return {"session_id": "test", "transcript_path": "/dev/null", "cwd": project, "permission_mode": "default",
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


def test_guard_cases(p):
    print("\n== test_guard.py")
    cases = [
        ("Edit frozen test", "Edit", {"file_path": p + "/tests/test_refund_rounding.py", "old_string": "150", "new_string": "149"}, "deny"),
        ("Write frozen test (relative path)", "Write", {"file_path": "tests/test_refund_rounding.py", "content": "x"}, "deny"),
        ("Edit test inside frozen directory", "Edit", {"file_path": p + "/tests/regression/test_inc_031.py", "old_string": "True", "new_string": "1"}, "deny"),
        ("Write existing file matching frozen glob", "Write", {"file_path": p + "/spec/models/order_frozen_spec.rb", "content": "x"}, "deny"),
        ("Write new test inside frozen directory", "Write", {"file_path": p + "/tests/regression/test_inc_044.py", "content": "def test_inc_044():\n    assert True\n"}, "pass"),
        ("Write new file matching frozen glob", "Write", {"file_path": p + "/spec/models/refund_frozen_spec.rb", "content": "x"}, "pass"),
        ("Edit the frozen list itself", "Edit", {"file_path": p + "/.claude/frozen-tests.txt", "old_string": "tests/regression/\n", "new_string": ""}, "deny"),
        ("Edit adds @pytest.mark.skip", "Edit", {"file_path": p + "/tests/test_cart.py", "old_string": "def test_total():", "new_string": "@pytest.mark.skip(reason='flaky')\ndef test_total():"}, "ask"),
        ("Edit adds it.only (focus)", "Edit", {"file_path": p + "/web/cart.test.ts", "old_string": "it('adds item', () => {", "new_string": "it.only('adds item', () => {"}, "ask"),
        ("Edit adds Go t.Skip", "Edit", {"file_path": p + "/pkg/cart/cart_test.go", "old_string": "func TestTotal(t *testing.T) {", "new_string": "func TestTotal(t *testing.T) {\n\tt.Skip(\"later\")"}, "ask"),
        ("Edit adds JUnit @Disabled", "Edit", {"file_path": p + "/src/test/java/CartTest.java", "old_string": "@Test", "new_string": "@Disabled\n    @Test"}, "ask"),
        ("Edit removes a test case", "Edit", {"file_path": p + "/tests/test_cart.py", "old_string": "def test_empty():\n    assert [] == []\n", "new_string": ""}, "ask"),
        ("Edit renames a test (count unchanged)", "Edit", {"file_path": p + "/tests/test_cart.py", "old_string": "def test_empty():", "new_string": "def test_empty_cart():"}, "pass"),
        ("Write existing test adding skip (compares disk)", "Write", {"file_path": p + "/tests/test_cart.py", "content": "import pytest\n\n@pytest.mark.skip\ndef test_total():\n    assert 1 + 1 == 2\n\ndef test_empty():\n    assert [] == []\n"}, "ask"),
        ("Write brand-new test file", "Write", {"file_path": p + "/tests/test_new.py", "content": "def test_new():\n    assert True\n"}, "pass"),
        ("Edit source file containing 'it.skip(' text", "Edit", {"file_path": p + "/src/pricing.py", "old_string": "int(", "new_string": "round(  # not it.skip(\n"}, "pass"),
        ("Edit pytest.ini adds --deselect", "Edit", {"file_path": p + "/pytest.ini", "old_string": "addopts = -q", "new_string": "addopts = -q --deselect tests/test_cart.py::test_total"}, "ask"),
        ("MultiEdit (legacy) adds xit", "MultiEdit", {"file_path": p + "/web/cart.spec.js", "edits": [{"old_string": "it('a'", "new_string": "xit('a'"}]}, "ask"),
        ("NotebookEdit outside tests", "NotebookEdit", {"notebook_path": p + "/notebooks/eda.ipynb", "new_source": "print(1)"}, "pass"),
    ]
    for name, tool, tin, expected in cases:
        check(name, TEST_GUARD, pre(tool, tin, p), expected, p)
    bash = [
        ("Bash rm frozen test", "rm tests/test_refund_rounding.py", "deny"),
        ("Bash sed -i on frozen test", "sed -i '' 's/150/149/' tests/test_refund_rounding.py", "deny"),
        ("Bash git checkout -- frozen test", "git checkout -- tests/test_refund_rounding.py", "deny"),
        ("Bash redirect over frozen test", "echo 'def test_x(): pass' > tests/test_refund_rounding.py", "deny"),
        ("Bash mv frozen directory file", "mv tests/regression/test_inc_031.py /tmp/", "deny"),
        ("Bash rm inside sh -c", "bash -c \"rm -f tests/test_refund_rounding.py\"", "deny"),
        ("Bash runs frozen test with redirection", "python3 -m pytest tests/test_refund_rounding.py 2>&1 | tail -5", "pass"),
        ("Bash reads frozen test", "cat tests/test_refund_rounding.py", "pass"),
        ("Bash copies frozen test elsewhere", "cp tests/test_refund_rounding.py /tmp/copy.py", "pass"),
    ]
    for name, command, expected in bash:
        check(name, TEST_GUARD, pre("Bash", {"command": command}, p), expected, p)
    check("Unreadable hook input", TEST_GUARD, None, "ask", p, raw="{not json")


def prod_guard_cases(p_main, p_feature):
    print("\n== prod_boundary_guard.py")
    deny = [
        "kubectl apply -f k8s/ --context prod-eu",
        "kubectl config use-context prod-eu && kubectl apply -f x.yaml",
        "helm upgrade --install api ./chart -n production",
        "terraform apply -var-file=envs/prod.tfvars",
        "terraform -chdir=infra/prod destroy",
        "aws ecs update-service --cluster prod-api --service web --force-new-deployment",
        "gcloud config set project acme-prod",
        "vercel --prod",
        "npx vercel deploy --prod",
        "ansible-playbook -i inventories/prod site.yml",
        "bash -c \"kubectl delete ns payments --context prod\"",
        "psql -h prod-db.internal -U app",
        "DATABASE_URL=$PROD_DATABASE_URL alembic upgrade head",
        "ssh deploy@prod-web-1",
        "export AWS_PROFILE=prod",
        "docker push registry.example.com/api:prod",
        "gh workflow run deploy.yml -f environment=production",
        "cat .env",
        "source .env.local",
        "grep API_KEY config/secrets.yml",
        "cp ~/.aws/credentials /tmp/c",
        "aws sts assume-role --role-arn arn:aws:iam::1:role/x --role-session-name y",
        "gh auth token",
        "kubectl get secret db -o jsonpath='{.data.password}'",
        "git push origin HEAD:main",
        "git push --force origin master",
        "echo '{}' > .claude/settings.json",
        "sed -i 's/deny/allow/' .claude/settings.json",
        "rm -rf .claude/hooks",
        "rm -rf .claude",
        "claude -p 'fix it' --dangerously-skip-permissions",
    ]
    ask = [
        "kubectl get pods -n prod",
        "kubectl logs deploy/api --context prod",
        "terraform plan -var-file=envs/prod.tfvars",
        "terraform apply",
        "kubectl apply -f k8s/",
        "git push --force origin feature/refund-rounding",
        "git push origin v1.4.0",
        "git push --tags",
        "git commit --no-verify -m wip",
        "gh pr merge 42 --squash",
        "gh workflow run ci.yml",
        "docker push registry.example.com/api:sha-abc123",
        "printenv",
        "env",
        "openssl x509 -in tests/fixtures/cert.pem -noout -text",
    ]
    allow = [
        "make verify",
        "git status",
        "git log --oneline -5",
        "kubectl apply -f k8s/ --context kind-dev",
        "terraform apply -var-file=envs/staging.tfvars",
        "helm upgrade api ./chart -n staging",
        "firebase deploy --project my-app-staging",
        "kubectl get pods",
        "aws s3 ls",
        "npm run build:prod",
        "NODE_ENV=production npm run build",
        "cp .env.example .env",
        "cat .env.example",
        "echo '.env' >> .gitignore",
        "docker compose --env-file .env up -d",
        "grep -rn 'prod' src/",
        "psql -h localhost -U app",
        "cat .claude/settings.json",
        "python3 -m pytest -q tests/",
    ]
    for command in deny:
        check("deny  " + command, PROD_GUARD, pre("Bash", {"command": command}, p_feature), "deny", p_feature)
    for command in ask:
        check("ask   " + command, PROD_GUARD, pre("Bash", {"command": command}, p_feature), "ask", p_feature)
    for command in allow:
        check("pass  " + command, PROD_GUARD, pre("Bash", {"command": command}, p_feature), "pass", p_feature)
    check("deny  git push (current branch is main)", PROD_GUARD, pre("Bash", {"command": "git push"}, p_main), "deny", p_main)
    check("pass  git push -u origin feature branch", PROD_GUARD,
          pre("Bash", {"command": "git push -u origin feature/refund-rounding"}, p_feature), "pass", p_feature)
    check("pass  non-Bash tool is ignored", PROD_GUARD, pre("Read", {"file_path": ".env"}, p_feature), "pass", p_feature)


def stop_cases(tmp):
    print("\n== stop_verify_gate.py")
    repo = os.path.join(tmp, "stop-repo")
    os.makedirs(repo)
    runs, fail_flag, state = os.path.join(tmp, "runs.log"), os.path.join(tmp, "fail.flag"), os.path.join(tmp, "state")
    with open(os.path.join(repo, "Makefile"), "w") as fh:
        fh.write("verify:\n\t@echo run >> \"$(RUNS_FILE)\"\n"
                 "\t@if [ -f \"$(FAIL_FLAG)\" ]; then echo 'FAILED tests/test_refund_rounding.py::test_half_up - assert 149 == 150'; exit 1; fi\n"
                 "\t@echo 'verify: OK'\n")
    os.makedirs(os.path.join(repo, "docs", "changes", "PAY-1"))
    sh(repo, "git", "init", "-q", "-b", "feature/x")
    sh(repo, "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
    sh(repo, "git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init")
    env = {"RUNS_FILE": runs, "FAIL_FLAG": fail_flag, "CLAUDE_VERIFY_STATE_DIR": state}

    def stop(session, extra=None):
        payload = {"session_id": session, "transcript_path": "/dev/null", "cwd": repo,
                   "permission_mode": "default", "hook_event_name": "Stop", "stop_hook_active": False}
        return dict(env, **(extra or {})), payload

    def run_count():
        return sum(1 for _ in open(runs)) if os.path.exists(runs) else 0

    e, pl = stop("s1")
    check("clean tree: allow, verify not run", STOP_GATE, pl, "pass", repo, e)
    with open(os.path.join(repo, "docs", "changes", "PAY-1", "intent.md"), "w") as fh:
        fh.write("# intent\n")
    check("only docs/changes artifacts changed: allow", STOP_GATE, pl, "pass", repo, e)
    results.append(run_count() == 0)
    print("{} verify was not run for clean / artifact-only trees".format("PASS" if run_count() == 0 else "FAIL"))

    with open(os.path.join(repo, "pricing.py"), "w") as fh:
        fh.write("x = 1\n")
    check("dirty tree, verify passes: allow", STOP_GATE, pl, "pass", repo, e)
    check("unchanged since last pass: allow without re-running", STOP_GATE, pl, "pass", repo, e)
    results.append(run_count() == 1)
    print("{} verify ran once for two stops on the same tree (runs={})".format("PASS" if run_count() == 1 else "FAIL", run_count()))

    open(fail_flag, "w").close()
    with open(os.path.join(repo, "pricing.py"), "w") as fh:
        fh.write("x = 2\n")
    first = check("verify fails: block 1", STOP_GATE, pl, "block", repo, e)
    results.append(bool(first) and "assert 149 == 150" in first.get("reason", "") and "1 of 3" in first.get("reason", ""))
    print("{} block reason carries the failing output and the attempt count".format("PASS" if results[-1] else "FAIL"))
    check("unchanged since failure: block 2 from saved output", STOP_GATE, pl, "block", repo, e)
    results.append(run_count() == 2)
    print("{} failed verify was not re-run on an unchanged tree (runs={})".format("PASS" if run_count() == 2 else "FAIL", run_count()))
    with open(os.path.join(repo, "pricing.py"), "w") as fh:
        fh.write("x = 3\n")
    check("still failing after edit: block 3", STOP_GATE, pl, "block", repo, e)
    check("cap reached: allow and warn the user", STOP_GATE, pl, "warn", repo, e)
    e2, pl2 = stop("s2")
    check("new session_id has its own cap: block", STOP_GATE, pl2, "block", repo, e2)
    os.remove(fail_flag)
    with open(os.path.join(repo, "pricing.py"), "w") as fh:
        fh.write("x = 4\n")
    check("fixed: allow", STOP_GATE, pl2, "pass", repo, e2)

    e3, pl3 = stop("s3", {"CLAUDE_VERIFY_CMD": "sleep 5", "CLAUDE_VERIFY_TIMEOUT": "1"})
    timed = check("verify times out: block", STOP_GATE, pl3, "block", repo, e3)
    results.append(bool(timed) and "timed out" in timed.get("reason", ""))
    print("{} timeout is reported to the agent".format("PASS" if results[-1] else "FAIL"))

    bare = os.path.join(tmp, "no-makefile")
    os.makedirs(bare)
    sh(bare, "git", "init", "-q")
    with open(os.path.join(bare, "a.txt"), "w") as fh:
        fh.write("a")
    e4, pl4 = stop("s4")
    pl4["cwd"] = bare
    check("no Makefile: allow and warn", STOP_GATE, pl4, "warn", bare, e4)
    plain = os.path.join(tmp, "not-a-repo")
    os.makedirs(plain)
    pl5 = dict(pl4, cwd=plain)
    check("not a git repo: allow", STOP_GATE, pl5, "pass", plain, e4)
    check("unreadable input: allow", STOP_GATE, None, "pass", repo, e, raw="nope")


def main():
    tmp = tempfile.mkdtemp(prefix="hook-tests-")
    try:
        p_main, p_feature = os.path.join(tmp, "repo-main"), os.path.join(tmp, "repo-feature")
        make_repo(p_main, "main")
        make_repo(p_feature, "feature/refund-rounding")
        test_guard_cases(p_feature)
        prod_guard_cases(p_main, p_feature)
        stop_cases(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = results.count(False)
    print("\n{} checks, {} failed".format(len(results), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
