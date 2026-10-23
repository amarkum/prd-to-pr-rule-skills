#!/usr/bin/env python3
"""Stop hook (Agentic SDLC starter kit): no "done" while `make verify` fails.

When the agent tries to finish and the git tree is dirty, run the verify command
(CLAUDE_VERIFY_CMD, default "make verify"). If it fails, block the stop and hand
the failing output back to the agent so it keeps working. The hook blocks at most
CLAUDE_VERIFY_MAX_BLOCKS times (default 3) per session_id, then lets the session
end and warns the user, so a stuck agent cannot loop.

The run is skipped when the tree is clean, when every changed path matches
CLAUDE_VERIFY_SKIP_REGEX (default: change artifacts under docs/changes/), or when
nothing changed since the last passing run in this session. If nothing changed
since the last failing run, it blocks again with the saved output instead of
running the command again.

Other settings: CLAUDE_VERIFY_TIMEOUT (seconds, default 540; keep it below the
hook's timeout in settings.json) and CLAUDE_VERIFY_STATE_DIR (default: a folder
in the system temp dir).

Stdlib only, Python 3.8+. Self-test: python3 .claude/hooks/tests/run_hook_tests.py
"""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import project_root, read_payload  # noqa: E402

TAIL_LINES = 80
TAIL_CHARS = 6000


def git(root, *args):
    try:
        out = subprocess.run(["git"] + list(args), cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


def changed_paths(porcelain):
    """Paths from `git status --porcelain=v1 -z` output."""
    parts, paths, i = porcelain.split("\0"), [], 0
    while i < len(parts):
        entry = parts[i]
        if entry:
            paths.append(entry[3:])
            if entry[0] in "RC":
                i += 1  # a rename or copy is followed by its source path
        i += 1
    return paths


def fingerprint(root, porcelain, paths):
    digest = hashlib.sha256(porcelain.encode())
    digest.update((git(root, "diff", "HEAD", "--binary") or git(root, "diff", "--binary") or "").encode())
    for path in paths:
        full = os.path.join(root, path)
        try:
            stat = os.stat(full)
            digest.update("{}:{}:{}".format(path, stat.st_size, stat.st_mtime_ns).encode())
        except OSError:
            digest.update(path.encode())
    return digest.hexdigest()


def state_file(session_id):
    folder = os.environ.get("CLAUDE_VERIFY_STATE_DIR") or os.path.join(tempfile.gettempdir(), "claude-verify-gate")
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:128] or "unknown"
    return os.path.join(folder, safe + ".json")


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, path)


def run_verify(command, root, timeout):
    proc = subprocess.Popen(command, shell=True, cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode == 0, out.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            proc.kill()
        out, _ = proc.communicate()
        return False, out.decode("utf-8", "replace") + "\n[verify gate] timed out after {}s".format(timeout)


def tail(text):
    lines = text.rstrip().splitlines()[-TAIL_LINES:]
    return "\n".join(lines)[-TAIL_CHARS:]


def main():
    payload = read_payload()
    if payload is None:
        return  # never trap a session because of unreadable input
    root = project_root(payload)
    porcelain = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if not porcelain:
        return  # clean tree, or not a git repository
    paths = changed_paths(porcelain)
    skip = os.environ.get("CLAUDE_VERIFY_SKIP_REGEX", r"^docs/changes/")
    if skip and all(re.search(skip, p) for p in paths):
        return

    command = os.environ.get("CLAUDE_VERIFY_CMD", "make verify")
    if command == "make verify" and not any(
            os.path.exists(os.path.join(root, f)) for f in ("Makefile", "makefile", "GNUmakefile")):
        print(json.dumps({"systemMessage": "Verify gate: no Makefile here, so `make verify` was not run. "
                                           "Install Makefile.template from the starter kit."}))
        return

    path = state_file(str(payload.get("session_id") or "unknown"))
    state = load(path)
    current = fingerprint(root, porcelain, paths)
    if state.get("last_pass") == current:
        return
    max_blocks = int(os.environ.get("CLAUDE_VERIFY_MAX_BLOCKS", "3"))
    blocks = int(state.get("blocks", 0))
    if blocks >= max_blocks:
        message = ("Verify gate: `{}` still fails after {} blocked stops in this session, so the session "
                   "may end. The change is not done: do not open or merge a PR until it passes.").format(command, blocks)
        print(message, file=sys.stderr)
        print(json.dumps({"systemMessage": message}))
        return

    if state.get("last_fail") == current:
        output = state.get("last_fail_output", "")  # nothing changed since it failed; don't re-run
    else:
        ok, output = run_verify(command, root, int(os.environ.get("CLAUDE_VERIFY_TIMEOUT", "540")))
        if ok:
            state["last_pass"] = current
            save(path, state)
            return
        output = tail(output)
        state["last_fail"], state["last_fail_output"] = current, output
    state["blocks"] = blocks + 1
    save(path, state)
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Verify gate (block {n} of {m}): `{cmd}` failed, so this change is not done.\n"
            "Fix the cause, then re-run `{cmd}` and finish only when it passes. Do not skip, weaken "
            "or delete tests to get there. If the failure is unrelated to your change or needs a human "
            "decision, say so plainly and stop.\n\nLast lines of output:\n{out}"
        ).format(n=blocks + 1, m=max_blocks, cmd=command, out=output),
    }))


if __name__ == "__main__":
    main()
