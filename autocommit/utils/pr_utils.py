"""PR creation and auto-merge utilities for GitHub, GitLab, etc."""

import re
import subprocess
from typing import Optional


_VALID_MERGE_METHODS = frozenset({"merge", "squash", "rebase"})


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


def _get_remote_url(repo_path: str) -> str:
    """Run ``git remote get-url origin`` and return the URL."""
    code, out, err = _run("git remote get-url origin", repo_path)
    if code != 0:
        raise RuntimeError(f"Cannot get remote origin URL: {err}")
    return out


def _create_pr_raw(
    *,
    repo_path: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
) -> tuple:
    """Create a pull request and return the raw PR object plus provider name.

    Returns ``(provider, raw_pr_or_mr)`` where *raw_pr_or_mr* is the
    PyGithub ``PullRequest`` or python-gitlab ``ProjectMergeRequest``.
    The caller can use the object to enable auto-merge or access
    additional attributes.

    Raises ``RuntimeError`` if the library is not installed, the token
    is invalid, the remote URL is missing or unparseable, or the API
    call fails.
    """
    remote_url = _get_remote_url(repo_path)
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
        return provider, pr

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
        return provider, mr

    else:
        raise RuntimeError(f"Unsupported provider: {provider}")


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
    provider, pr_obj = _create_pr_raw(
        repo_path=repo_path,
        token=token,
        head_branch=head_branch,
        base_branch=base_branch,
        title=title,
        body=body,
    )
    if provider == "github":
        return pr_obj.html_url
    elif provider == "gitlab":
        return pr_obj.web_url
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")


def create_pr_and_auto_merge(
    *,
    repo_path: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
    auto_merge: bool = False,
    merge_method: str = "merge",
) -> str:
    """Create a pull request and optionally enable auto-merge.

    When *auto_merge* is ``True``, uses the native auto-merge API of the
    hosting provider (GitHub: ``enable_auto_merge``, GitLab:
    ``merge_when_pipeline_succeeds``).

    Parameters
    ----------
    merge_method : str
        One of ``"merge"``, ``"squash"``, or ``"rebase"``.
        Ignored when *auto_merge* is ``False``.

    Returns
    -------
    str
        The PR URL.

    Raises
    ------
    RuntimeError
        If *auto_merge* is ``True`` but the provider or library version
        does not support it, or if the merge method is invalid.
    """
    if auto_merge and merge_method not in _VALID_MERGE_METHODS:
        raise RuntimeError(
            f"Invalid merge_method: {merge_method!r}. "
            f"Valid options: {', '.join(sorted(_VALID_MERGE_METHODS))}"
        )

    provider, pr_obj = _create_pr_raw(
        repo_path=repo_path,
        token=token,
        head_branch=head_branch,
        base_branch=base_branch,
        title=title,
        body=body,
    )

    if auto_merge:
        _enable_auto_merge(provider, pr_obj, merge_method)

    if provider == "github":
        return pr_obj.html_url
    elif provider == "gitlab":
        return pr_obj.web_url
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")


def _enable_auto_merge(provider: str, pr_obj, merge_method: str) -> None:
    """Call the provider's native auto-merge API on the PR/MR object.

    Raises ``RuntimeError`` if the operation is not supported.
    """
    if provider == "github":
        _enable_github_auto_merge(pr_obj, merge_method)
    elif provider == "gitlab":
        _enable_gitlab_auto_merge(pr_obj, merge_method)
    else:
        raise RuntimeError(
            f"Auto-merge is not supported for provider {provider!r}."
        )


def _enable_github_auto_merge(pr, merge_method: str) -> None:
    """Enable auto-merge on a GitHub PR via PyGithub.

    PyGithub 2.x+ supports ``enable_automerge``.
    """
    method_map = {
        "merge": "MERGE",
        "squash": "SQUASH",
        "rebase": "REBASE",
    }
    github_method = method_map[merge_method]
    try:
        pr.enable_automerge(merge_method=github_method)
    except AttributeError:
        raise RuntimeError(
            "Your PyGithub version does not support enable_automerge. "
            "Upgrade with: pip install --upgrade PyGithub>=2.0"
        )


def _enable_gitlab_auto_merge(mr, merge_method: str) -> None:
    """Enable 'merge when pipeline succeeds' on a GitLab MR.

    python-gitlab 4.x+ supports ``merge_when_pipeline_succeeds``.
    Note: GitLab uses the project's default merge method; the
    *merge_method* parameter is noted for future compatibility.
    """
    try:
        mr.merge_when_pipeline_succeeds = True
        mr.save()
    except AttributeError:
        raise RuntimeError(
            "Your python-gitlab version does not support "
            "merge_when_pipeline_succeeds. "
            "Upgrade with: pip install --upgrade python-gitlab>=4.0"
        )
