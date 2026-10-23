#!/usr/bin/env python3
"""PreToolUse production-boundary guard for Bash (Agentic SDLC starter kit).

Agents have full autonomy in dev and QA, autonomy plus policy checks in staging,
and never cross into production on their own. This hook holds that line for
shell commands.

deny  Commands that change production (deploy, apply, migrate, scale, open a DB or
      remote shell), push straight to a protected branch, read secret files or
      mint credentials, or tamper with the agent's own guardrails.
ask   Commands that read from production, change infrastructure without naming a
      non-production environment, force-push, push tags, start deploy workflows,
      merge PRs, skip git hooks, read key files, or print the whole environment.
pass  Everything else: print nothing, exit 0, and the normal permission flow decides.

This is a seatbelt, not the boundary. The boundary is that agent sessions never
hold production credentials (short-lived, environment-scoped credentials, a
sandbox and a network allowlist). Tune the names below to your estate, or set
PROD_NAME_REGEX / NONPROD_NAME_REGEX / PROTECTED_BRANCH_REGEX in the environment.

Stdlib only, Python 3.8+. Self-test: python3 .claude/hooks/tests/run_hook_tests.py
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import (command_name, emit_pretooluse, mutation_targets,  # noqa: E402
                      project_root, read_payload, split_segments, tokens)

I = re.IGNORECASE
PROD = re.compile(os.environ.get(
    "PROD_NAME_REGEX", r"(?<![a-z0-9])(?:prod|production|prd)(?![a-z0-9])"), I)
NONPROD = re.compile(os.environ.get(
    "NONPROD_NAME_REGEX",
    r"(?<![a-z0-9])(?:dev|development|qa|test|testing|staging|stage|stg|sandbox|local|localhost"
    r"|preview|ci|kind|minikube|docker-desktop|emulators?|offline)(?![a-z0-9])"), I)
PROTECTED_BRANCH = re.compile(os.environ.get(
    "PROTECTED_BRANCH_REGEX", r"^(?:main|master|trunk|production|prod|release(?:/.*)?)$"))

INFRA = {
    "kubectl", "oc", "helm", "helmfile", "kustomize", "argocd", "flux", "terraform", "terragrunt",
    "tofu", "pulumi", "cdk", "cdktf", "sam", "serverless", "sls", "eb", "fly", "flyctl", "vercel",
    "netlify", "firebase", "heroku", "gcloud", "gsutil", "aws", "az", "doctl", "ansible",
    "ansible-playbook", "nomad", "skaffold", "eksctl", "wrangler", "railway", "supabase",
}
DB_CLIENTS = {
    "psql", "pg_dump", "pg_dumpall", "pg_restore", "pgcli", "mysql", "mysqldump", "mycli", "mariadb",
    "mongosh", "mongo", "mongodump", "mongorestore", "mongoexport", "redis-cli", "sqlcmd", "cqlsh",
    "clickhouse-client", "sqlplus", "bq", "snowsql", "cockroach", "usql",
}
REMOTE = {"ssh", "scp", "sftp", "rsync", "mosh", "telnet"}
MIGRATION = re.compile(
    r"\b(?:alembic\s+(?:upgrade|downgrade|stamp)|flyway\s+\w+|liquibase\s+\w+"
    r"|prisma\s+(?:migrate\s+\w+|db\s+(?:push|execute))|knex\s+migrate|sequelize\s+db:migrate"
    r"|rails\s+db:\w+|rake\s+db:\w+|manage\.py\s+(?:migrate|flush|dbshell|loaddata)"
    r"|goose\s+\w+|dbmate\s+\w+|atlas\s+(?:migrate|schema)\s+apply)\b", I)

# The first verb after an infra tool decides whether the command reads or changes things.
READ_VERBS = {
    "get", "describe", "list", "ls", "show", "logs", "log", "top", "status", "plan", "diff",
    "history", "version", "explain", "whoami", "info", "output", "validate", "preview", "search",
    "template", "lint", "events", "wait", "inspect", "view", "fmt", "graph", "cat",
}
MUTATING_VERBS = {
    "apply", "create", "delete", "destroy", "patch", "replace", "scale", "edit", "set", "unset",
    "label", "annotate", "drain", "cordon", "uncordon", "taint", "untaint", "exec", "run", "expose",
    "autoscale", "port", "use", "install", "upgrade", "uninstall", "rollback", "undo", "import",
    "up", "update", "refresh", "deploy", "remove", "rm", "mv", "cp", "sync", "promote", "push",
    "terminate", "start", "stop", "reboot", "restart", "modify", "put", "attach", "detach",
    "invoke", "restore", "register", "deregister", "enable", "disable", "associate", "disassociate",
    "authorize", "revoke", "send", "publish", "execute", "reconcile", "suspend", "resume",
    "release", "ssh", "scp", "select", "purge", "reset", "kill", "evict", "pull",
}

TARGET_ENV_VARS = re.compile(
    r"(?:^|\s)(?:export\s+)?(?:KUBECONFIG|KUBE_CONTEXT|AWS_PROFILE|AWS_DEFAULT_PROFILE"
    r"|GOOGLE_CLOUD_PROJECT|CLOUDSDK_CORE_PROJECT|CLOUDSDK_ACTIVE_CONFIG_NAME|ARM_SUBSCRIPTION_ID"
    r"|AZURE_SUBSCRIPTION_ID|TF_WORKSPACE|PULUMI_STACK|DATABASE_URL|PGHOST|PGDATABASE|PGSERVICE"
    r"|MYSQL_HOST|MONGODB_URI|MONGO_URL|REDIS_URL|VAULT_ADDR|DOCKER_CONTEXT|DOCKER_HOST)=(\S*)")

CREDENTIALS = [re.compile(p, I) for p in (
    r"\baws\s+configure\s+(?:get|export-credentials)\b",
    r"\baws\s+sts\s+(?:get-session-token|assume-role\S*|get-federation-token)\b",
    r"\baws\s+secretsmanager\s+get-secret-value\b",
    r"\baws\s+ssm\s+get-parameters?\b.*--with-decryption",
    r"\bgcloud\s+(?:auth\s+(?:application-default\s+)?print-(?:access|identity)-token|secrets\s+versions\s+access)\b",
    r"\baz\s+(?:account\s+get-access-token|keyvault\s+secret\s+show)\b",
    r"\bgh\s+auth\s+token\b",
    r"\bvault\s+(?:read|kv\s+get|token\s+create|login)\b",
    r"\bop\s+(?:read|item\s+get|inject)\b",
    r"\bsecurity\s+find-(?:generic|internet)-password\b",
    r"\bkubectl\s+get\s+secrets?\b.*-o\s*=?\s*(?:yaml|json|jsonpath|go-template)",
    r"\b(?:doppler|infisical)\s+secrets\b",
)]
SECRET_FILE = re.compile(
    r"(?:^|/)(?:\.env(?!\.(?:example|sample|template|dist|defaults)$)(?:\.[\w-]+)?|\.envrc"
    r"|id_(?:rsa|dsa|ecdsa|ed25519)|\.netrc|\.pypirc|\.git-credentials|credentials\.json"
    r"|secrets?\.(?:ya?ml|json|env|txt|toml))$"
    r"|(?:^|/)\.aws/(?:credentials|config)$|(?:^|/)\.kube/config$|(?:^|/)\.docker/config\.json$"
    r"|(?:^|/)\.config/gcloud/|(?:^|/)\.ssh/|(?:^|/)secrets?/")
KEY_FILE = re.compile(r"\.(?:pem|p12|pfx|key|jks|keystore)$|(?:^|/)\.npmrc$")
# Commands that only touch file names or metadata, never contents.
METADATA_ONLY = {"echo", "printf", "ls", "touch", "rm", "stat", "file", "test", "[", "mkdir",
                 "chmod", "chown", "which", "type", "basename", "dirname", "realpath"}
GUARDRAIL_FILE = re.compile(
    r"(?:^|/)\.claude/?$|(?:^|/)\.claude/(?:settings(?:\.local)?\.json|hooks(?:/|$)|frozen-tests\.txt)"
    r"|managed-settings\.json")
CLAUDE_UNSAFE = re.compile(
    r"\bclaude\b.*(?:--dangerously-skip-permissions|--allow-dangerously-skip-permissions"
    r"|bypassPermissions|--bare\b|--safe-mode\b|--setting-sources\b)", I)

DENY, ASK = 2, 1


def first_verb(words):
    """'read', 'mutate' or None for the words that follow an infra tool."""
    for word in words[:6]:
        if "/" in word or "=" in word:
            continue
        for part in re.split(r"[-:]", word.lower()):
            if part in MUTATING_VERBS:
                return "mutate"
            if part in READ_VERBS:
                return "read"
    return None


def verdicts_for(segment, root):
    """Yield (severity, reason) pairs for one simple command."""
    toks = tokens(segment)
    name, rest = command_name(toks)
    bases = [os.path.basename(t) for t in toks]
    has_prod = bool(PROD.search(segment))

    # Guardrails: hooks, settings and the frozen-test list belong to humans.
    for target in mutation_targets(segment):
        if GUARDRAIL_FILE.search(target):
            yield DENY, "modifies agent guardrails ({}); change them in a reviewed PR".format(target)
    if CLAUDE_UNSAFE.search(segment):
        yield DENY, "starts Claude Code with permissions or hooks switched off"

    # Secrets and credentials.
    if any(p.search(segment) for p in CREDENTIALS):
        yield DENY, "mints or reveals credentials; agent sessions work without them"
    git_meta = name == "git" and rest[:1] in (["status"], ["check-ignore"], ["ls-files"], ["rm"])
    if name not in METADATA_ONLY and not git_meta:
        args = rest[:-1] if name in ("cp", "mv", "install") else rest  # a copy's destination is not read
        skip_next = False
        for tok in args:
            if skip_next or tok.startswith("--env-file"):
                skip_next = tok == "--env-file"
                continue
            value = tok.split("=", 1)[-1]
            if SECRET_FILE.search(value):
                yield DENY, "reads a secret or credential file ({})".format(tok)
                break
            if KEY_FILE.search(value):
                yield ASK, "reads a key or certificate file ({})".format(tok)
                break
    if toks in (["env"], ["printenv"], ["export", "-p"], ["set"]):
        yield ASK, "prints the whole environment, which may contain tokens"

    # Pointing the session at production.
    for match in TARGET_ENV_VARS.finditer(segment):
        if PROD.search(match.group(1)):
            yield DENY, "points the session at a production target ({})".format(match.group(0).strip())

    # Infrastructure and deploy tooling.
    for i, base in enumerate(bases):
        if base not in INFRA:
            continue
        verb = first_verb([t for t in toks[i + 1:] if not t.startswith("-")])
        if has_prod and verb == "read":
            yield ASK, "reads from production; prefer the read-only observability tools"
        elif has_prod:
            yield DENY, "changes production infrastructure; production needs a human or policy gate"
        elif verb == "mutate" and not NONPROD.search(segment):
            yield ASK, "changes infrastructure without naming a non-production environment"
        break

    if has_prod and DB_CLIENTS.intersection(bases):
        yield DENY, "opens a database session against production"
    if has_prod and MIGRATION.search(segment):
        yield DENY, "runs a schema migration against production"
    if has_prod and REMOTE.intersection(bases):
        yield DENY, "opens a remote session to a production host"

    # Docker images and contexts.
    if name in ("docker", "podman"):
        if re.search(r"\b(?:push|context\s+use|stack\s+deploy|service\s+(?:update|rm|create))\b|--push\b", segment):
            if has_prod:
                yield DENY, "pushes or deploys to a production registry or context"
            else:
                yield ASK, "pushes an image or changes a Docker context"

    # GitHub CLI.
    if name == "gh":
        if re.search(r"\bworkflow\s+run\b", segment):
            yield (DENY, "starts a production workflow") if has_prod else (ASK, "starts a CI/CD workflow")
        if re.search(r"\brelease\s+create\b|\bpr\s+merge\b|\bsecret\s+(?:set|delete)\b", segment):
            yield ASK, "releases, merges or changes repository secrets; the builder decides"

    if name == "git":
        for verdict in git_verdicts(rest, root):
            yield verdict


def git_verdicts(rest, root):
    if not rest:
        return
    if "--no-verify" in rest or (rest[0] == "commit" and "-n" in rest) or "core.hooksPath" in rest:
        yield ASK, "skips or replaces git hooks"
    if rest[0] != "push":
        return
    args = rest[1:]
    force = any(a in ("-f", "--force", "--mirror", "--force-if-includes")
                or a.startswith("--force-with-lease") for a in args)
    delete = any(a in ("-d", "--delete") for a in args)
    tags = any(a in ("--tags", "--follow-tags") for a in args)
    positional = [a for a in args if not a.startswith("-")]
    destinations = []
    for spec in positional[1:]:
        if spec.startswith("+"):
            force, spec = True, spec[1:]
        if spec.startswith(":"):
            delete = True
        dst = spec.split(":", 1)[1] if ":" in spec else spec
        if dst.startswith("refs/tags/") or re.match(r"^v\d", dst):
            tags = True
        destinations.append(dst.replace("refs/heads/", ""))
    if not destinations or "HEAD" in destinations:
        destinations = [d for d in destinations if d != "HEAD"] + [current_branch(root)]
    protected = [d for d in destinations if d and PROTECTED_BRANCH.match(d)]
    if protected and (force or delete):
        yield DENY, "force-pushes or deletes protected branch {}".format(protected[0])
    elif protected:
        yield DENY, "pushes straight to protected branch {}; push a feature branch and open a PR".format(protected[0])
    elif force:
        yield ASK, "force-push rewrites remote history"
    elif tags:
        yield ASK, "pushing tags can start a release"


def current_branch(root):
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def main():
    payload = read_payload()
    if payload is None:
        emit_pretooluse("ask", "Production-boundary guard could not read the hook input, so this "
                               "command was not checked. Review it manually.")
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command", "")
    root = project_root(payload)
    worst, reason = 0, ""
    for segment in split_segments(command):
        for severity, why in verdicts_for(segment, root):
            if severity > worst:
                worst, reason = severity, "{} (`{}`)".format(why, segment[:160])
    if worst == DENY:
        emit_pretooluse("deny", "Production boundary: this command {}. Agents stop at the production "
                                "boundary; hand this step to the builder or the release pipeline.".format(reason))
    if worst == ASK:
        emit_pretooluse("ask", "Production boundary: this command {}. Approve only if that is "
                               "intended.".format(reason))


if __name__ == "__main__":
    main()
