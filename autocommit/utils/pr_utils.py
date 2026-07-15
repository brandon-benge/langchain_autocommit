"""PR creation utilities for GitHub, GitLab, and other hosting providers."""

import re
import subprocess
from typing import Optional


def _run(cmd: str, cwd: str) -> tuple[int, str, str]:
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = p.communicate()
    return p.returncode, out.strip(), err.strip()


def _detect_provider(remote_url: str) -> str:
    """Detect hosting provider from remote URL.

    Returns ``'github'`` or ``'gitlab'``.

    Raises ``RuntimeError`` for unknown hosts.
    """
    host_match = re.search(r"@(?P<host>[^:]+):|//(?P<host2>[^/]+)", remote_url)
    if not host_match:
        raise RuntimeError(f"Cannot parse host from remote URL: {remote_url}")
    host = host_match.group("host") or host_match.group("host2")
    host_lower = host.lower()
    if "github" in host_lower:
        return "github"
    elif "gitlab" in host_lower:
        return "gitlab"
    raise RuntimeError(
        f"Unknown Git hosting provider: {host}. "
        f"Supported: github.com, gitlab.com"
    )


def _parse_owner_repo(remote_url: str) -> tuple[str, str]:
    """Parse (*owner*, *repo*) from a remote URL.

    Supports::

        git@github.com:owner/repo.git
        https://github.com/owner/repo.git
        https://github.com/owner/repo
    """
    url = remote_url
    if url.endswith(".git"):
        url = url[:-4]

    ssh_match = re.search(r"git@[^:]+:(.+?)/(.+?)$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    https_match = re.search(r"https?://[^/]+/(.+?)/(.+?)$", url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    raise RuntimeError(f"Unrecognized remote URL format: {remote_url}")


def create_pr(
    *,
    repo_path: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
) -> str:
    """Create a pull request and return its URL.

    Detects the hosting provider from the ``origin`` remote URL, then uses
    the appropriate Python library (``PyGithub`` / ``python-gitlab``) to
    create the PR.

    Raises
    ------
    RuntimeError
        If the provider library is not installed, the token is invalid, the
        remote URL is missing or unparseable, or the API call fails.
    """
    code, out, err = _run("git remote get-url origin", repo_path)
    if code != 0:
        raise RuntimeError(f"Cannot get remote origin URL: {err}")
    remote_url = out

    provider = _detect_provider(remote_url)
    owner, repo = _parse_owner_repo(remote_url)

    if provider == "github":
        try:
            from github import Github  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "PyGithub is required for PR creation on GitHub. "
                "Install it with: pip install autocommit[github]"
            )
        g = Github(token)
        gh_repo = g.get_repo(f"{owner}/{repo}")
        pr = gh_repo.create_pull(
            title=title,
            body=body,
            base=base_branch,
            head=head_branch,
        )
        return pr.html_url

    elif provider == "gitlab":
        try:
            import gitlab  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "python-gitlab is required for PR creation on GitLab. "
                "Install it with: pip install autocommit[gitlab]"
            )
        gl = gitlab.Gitlab(private_token=token)
        gl_project = gl.projects.get(f"{owner}/{repo}")
        mr = gl_project.mergerequests.create(
            {
                "source_branch": head_branch,
                "target_branch": base_branch,
                "title": title,
                "description": body,
            }
        )
        return mr.web_url

    else:
        raise RuntimeError(f"Unsupported provider: {provider}")
