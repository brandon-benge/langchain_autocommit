import os, subprocess, re, shlex
from typing import List, Tuple, Optional

def _run(cmd: str, cwd: Optional[str]=None) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out.strip(), err.strip()

def ensure_git_repo(cwd: str) -> None:
    code, out, err = _run("git rev-parse --is-inside-work-tree", cwd)
    if code != 0 or out.strip() != "true":
        raise RuntimeError(f"Not a git repository: {cwd} ({err})")

def current_branch(cwd: str) -> str:
    code, out, err = _run("git rev-parse --abbrev-ref HEAD", cwd)
    if code != 0:
        raise RuntimeError(err)
    return out.strip()

def changed_files(cwd: str) -> List[str]:
    # staged and unstaged
    code, out, err = _run("git status --porcelain", cwd)
    if code != 0:
        raise RuntimeError(err)
    files = []
    for line in out.splitlines():
        if not line: continue
        path = line[3:].strip()
        files.append(path)
    return files

def staged_diff_summary(cwd: str, include_patch: bool = True) -> str:
    code, out, err = _run("git diff --staged --name-status && echo '---' && git diff --staged --stat", cwd)
    if code != 0:
        raise RuntimeError(err)
    if include_patch:
        code2, patch, err2 = _run("git diff --staged", cwd)
        if code2 == 0 and patch.strip():
            out += "\n---PATCH---\n" + patch
    return out

def autostage_all(cwd: str) -> None:
    code, out, err = _run("git add -A", cwd)
    if code != 0:
        raise RuntimeError(err)

def commit(cwd: str, subject: str, body: str, signoff: bool=False, amend: bool=False) -> None:
    args = ["git", "commit", "-m", subject, "-m", body]
    if signoff:
        args.append("--signoff")
    if amend:
        args.append("--amend")
        args.append("--no-edit")
    cmd = " ".join(shlex.quote(a) for a in args)
    code, out, err = _run(cmd, cwd)
    if code != 0:
        raise RuntimeError(err)

def push(cwd: str) -> None:
    code, out, err = _run("git push", cwd)
    if code != 0:
        raise RuntimeError(err)

_TYPE_RULES = [
    ("test", "all", ["tests/", "__tests__/"], ["_test.py", "_test.go", ".test.js", ".spec.ts", ".spec.js"]),
    ("fix", "all", ["fix/", "patches/", "hotfix/", "bugfix/"], []),
    ("docs", "any", ["docs/", "documentation/"], [".md", ".rst", ".tex"]),
    ("chore", "any", ["scripts/", ".github/", "ci/", "config/", "docker/", ".devcontainer/", ".vscode/"], [".sh", ".yml", ".yaml", "Dockerfile", "Makefile", "docker-compose"]),
]


def _path_matches(p: str, prefixes: list, extensions: list) -> bool:
    return any(p.startswith(prefix) for prefix in prefixes) or any(p.endswith(ext) for ext in extensions)


def infer_type_from_paths(paths: List[str]) -> str:
    if not paths:
        return "feat"
    for ctype, mode, prefixes, extensions in _TYPE_RULES:
        if mode == "all":
            if all(_path_matches(p, prefixes, extensions) for p in paths):
                return ctype
        elif mode == "any":
            if any(_path_matches(p, prefixes, extensions) for p in paths):
                return ctype
    if any(
        any(p.startswith(prefix) for prefix in ["src/", "app/", "api/", "routes/", "controllers/", "models/", "services/", "ui/", "components/", "pages/", "db/", "migrations/", "lib/", "utils/", "core/", "internal/", "middleware/", "middlewares/"])
        for p in paths
    ):
        return "feat"
    return "feat"

def infer_scope_from_cwd(cwd: str) -> str:
    return os.path.basename(os.path.abspath(cwd))

def find_ticket(branch: str, pattern: str) -> str:
    m = re.search(pattern, branch)
    return m.group(0) if m else ""
