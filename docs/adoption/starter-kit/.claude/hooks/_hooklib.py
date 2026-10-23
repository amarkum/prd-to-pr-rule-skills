"""Shared helpers for the Agentic SDLC starter-kit hooks.

Stdlib only, Python 3.8+. Imported by the hook scripts that sit next to it.
"""
import json
import os
import re
import shlex
import sys

# Wrappers that run another command; skipped when looking for the real command name.
WRAPPERS = {"sudo", "env", "command", "nohup", "time", "nice", "ionice", "exec", "xargs", "watch", "npx", "bunx"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}


def read_payload():
    """Parse the hook's JSON input from stdin. Returns None if it is unreadable."""
    try:
        return json.load(sys.stdin)
    except (ValueError, OSError):
        return None


def project_root(payload):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or (payload or {}).get("cwd") or os.getcwd()
    return os.path.realpath(root)


def rel_path(path, root):
    """Repo-relative POSIX path, or the cleaned input when it lies outside the repo."""
    if not path:
        return ""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    full = os.path.realpath(os.path.expanduser(full))
    rel = os.path.relpath(full, root)
    if rel.startswith(".."):
        return full.replace(os.sep, "/")
    return rel.replace(os.sep, "/")


def emit_pretooluse(decision, reason):
    """Print a PreToolUse decision (allow | deny | ask) and exit 0."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def split_segments(command):
    """Split a shell command into simple commands, recursing into `sh -c`,
    `$(...)` and backticks. Best effort: this is a guard, not a shell parser."""
    out = []
    for inner in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", command):
        out.extend(split_segments(inner[0] or inner[1]))
    parts = re.split(r"\|\||&&|;|\n|(?<![>|])\|(?!\|)|(?<![>&<0-9])&(?![>&])", command)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        out.append(part)
        toks = tokens(part)
        name, rest = command_name(toks)
        if name in SHELLS and "-c" in rest:
            idx = rest.index("-c")
            if idx + 1 < len(rest):
                out.extend(split_segments(rest[idx + 1]))
        if name == "eval" and rest:
            out.extend(split_segments(" ".join(rest)))
    return out


def tokens(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def command_name(toks):
    """Return (command basename, remaining tokens) after env assignments and wrappers."""
    i = 0
    while i < len(toks):
        tok = toks[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
            i += 1
            continue
        base = os.path.basename(tok)
        if base in WRAPPERS:
            i += 1
            # skip the wrapper's own flags, e.g. `nice -n 10`, `env -i`
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
            continue
        return base, toks[i + 1:]
    return "", []


def mutation_targets(segment):
    """Paths a simple shell command would create, overwrite, move or delete."""
    targets = []
    for match in re.finditer(r">{1,2}\|?\s*([^\s;&|<>]+)", segment):
        target = match.group(1)
        if not target.startswith("&"):
            targets.append(target)
    name, rest = command_name(tokens(segment))
    args = [t for t in rest if not t.startswith("-")]
    if name in ("rm", "unlink", "shred", "truncate", "tee", "touch", "chmod", "chown", "rmdir"):
        targets += args
    elif name == "mv":
        targets += args
    elif name in ("cp", "install", "ln", "rsync", "scp"):
        targets += args[-1:]
    elif name in ("sed", "gsed", "perl") and any(re.match(r"^(-[a-zA-Z]*i|--in-place)", t) for t in rest):
        targets += args
    elif name == "dd":
        targets += [t[3:] for t in rest if t.startswith("of=")]
    elif name == "git" and rest and rest[0] in ("rm", "mv", "checkout", "restore", "reset", "clean"):
        targets += [t for t in rest[1:] if not t.startswith("-")]
    return targets
