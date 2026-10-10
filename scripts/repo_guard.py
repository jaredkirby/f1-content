#!/usr/bin/env python3
"""Inspect Git's exact index, never print matched secret values.

A conservative publication tripwire, not a complete secret or licensing scanner.
Run before committing and on clean CI checkouts. Force-adding ignored files does
not bypass this guard. New source roots require an explicit policy change.
"""
from pathlib import PurePosixPath
import re
import subprocess
import sys

SOURCE_ROOTS = {"f1_pipeline", "scripts", "tests", "examples", "docs", "workflows", ".github", ".githooks"}
ROOT_FILES = {".gitignore", ".gitattributes", ".editorconfig", ".python-version",
              "AGENTS.md", "README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
              "THIRD_PARTY_NOTICES.md", "pyproject.toml", "requirements.txt"}
MAX_BYTES = 1024 * 1024
FORBIDDEN_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".aiff",
                      ".pdf", ".zip", ".gz", ".tar", ".pyc", ".pem", ".key"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "provider token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,})"),
    "signed URL": re.compile(r"[?&](?:sig|signature|token|auth|policy|key-pair-id|x-amz-signature)=[A-Za-z0-9%_~./+-]{8,}", re.I),
    "personal absolute path": re.compile(r"/Users" + r"/[^/\s\"']+/"),
    "private hosting address": re.compile(r"https?://[A-Za-z0-9.-]+\.chatgpt\.site\b"),
    "credential assignment": re.compile(r'''(?i)["']?(?:api_key|access_token|client_secret|password)["']?\s*[:=]\s*["'][A-Za-z0-9_+/=-]{24,}["']'''),
}


def inspect_blob(path, mode, blob):
    issues = []
    p = PurePosixPath(path)
    if len(p.parts) == 1:
        allowed = path in ROOT_FILES
    else:
        allowed = p.parts[0] in SOURCE_ROOTS
    if not allowed:
        issues.append("outside source allowlist")
    if mode not in ("100644", "100755"):
        issues.append("symlinks, submodules and unresolved entries are forbidden")
    if any(part in {".git", ".openai", ".codex", ".venv", "__pycache__"}
           or part.startswith('.env') or part == 'AGENTS.override.md' for part in p.parts):
        issues.append("local configuration or runtime path")
    if p.suffix.lower() in FORBIDDEN_SUFFIXES:
        issues.append("media, archive or credential file")
    if len(blob) > MAX_BYTES:
        issues.append("source file exceeds 1 MiB")
        return issues
    try:
        content = blob.decode("utf-8")
    except UnicodeDecodeError:
        return issues + ["non-UTF-8 binary content"]
    if '\0' in content:
        issues.append("binary content")
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            line = content.count('\n', 0, match.start()) + 1
            issues.append(f"{label} at line {line}")
    return issues


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    entries = git("ls-files", "--stage", "-z").split(b'\0')
    failures = []
    count = total = 0
    for entry in filter(None, entries):
        metadata, name = entry.split(b'\t', 1)
        mode, sha, stage = metadata.decode().split()
        path = name.decode('utf-8')
        count += 1
        if stage != '0':
            failures.append(f"{path}: unresolved merge")
            continue
        size = int(git('cat-file', '-s', sha)) if mode != '160000' else 0
        total += size
        if size > MAX_BYTES:
            failures.append(f"{path}: source file exceeds 1 MiB")
            continue
        blob = git('cat-file', 'blob', sha) if mode != '160000' else b''
        failures.extend(f"{path}: {issue}" for issue in inspect_blob(path, mode, blob))
    if not count:
        failures.append("No indexed source files; stage the intended source tree first.")
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print(f"Source guard passed: {count} indexed files, {total:,} bytes; no forbidden matches.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
