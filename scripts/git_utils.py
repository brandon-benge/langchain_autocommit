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

def staged_diff_summary(cwd: str) -> str:
    code, out, err = _run("git diff --staged --name-status && echo '---' && git diff --staged --stat", cwd)
    if code != 0:
        raise RuntimeError(err)
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

def infer_type_from_paths(paths: List[str]) -> str:
    """
    Heuristic: test/ docs/ build/ chore.
    """
    if all(p.startswith("tests/") or p.endswith("_test.py") for p in paths if paths):
        return "test"
    if any(p.startswith("docs/") or p.endswith(".md") for p in paths):
        return "docs"
    if any(p.startswith("scripts/") or p.startswith(".github/") or p.endswith(".sh") for p in paths):
        return "chore"
    return "feat"

def infer_scope_from_cwd(cwd: str) -> str:
    return os.path.basename(os.path.abspath(cwd))

def find_ticket(branch: str, pattern: str) -> str:
    m = re.search(pattern, branch)
    return m.group(0) if m else ""
