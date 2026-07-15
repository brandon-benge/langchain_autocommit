"""Tests for autocommit/utils/pr_utils.py."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from autocommit.utils.pr_utils import (
    _detect_provider,
    _parse_owner_repo,
    create_pr,
    create_pr_and_auto_merge,
)


# Fake module stubs for optional dependencies not installed in the test env.
import types


@pytest.fixture(autouse=True)
def _fake_optional_modules():
    """Install fake modules so patch("github.Github") and
    patch("gitlab.Gitlab") work without the real packages installed."""
    modules = {}
    if "github" not in sys.modules:
        gh_mod = types.ModuleType("github")
        gh_mod.Github = MagicMock()
        modules["github"] = gh_mod
    if "gitlab" not in sys.modules:
        gl_mod = types.ModuleType("gitlab")
        gl_mod.Gitlab = MagicMock()
        modules["gitlab"] = gl_mod
    with patch.dict(sys.modules, modules):
        yield


class TestDetectProvider:
    def test_github_ssh(self):
        assert _detect_provider("git@github.com:owner/repo.git") == "github"

    def test_github_https(self):
        assert _detect_provider("https://github.com/owner/repo.git") == "github"

    def test_github_enterprise(self):
        assert _detect_provider("https://github.mycompany.com/owner/repo.git") == "github"

    def test_gitlab_ssh(self):
        assert _detect_provider("git@gitlab.com:owner/repo.git") == "gitlab"

    def test_gitlab_https(self):
        assert _detect_provider("https://gitlab.com/owner/repo.git") == "gitlab"

    def test_gitlab_self_hosted(self):
        assert _detect_provider("https://gitlab.example.com/owner/repo.git") == "gitlab"

    def test_unknown_host(self):
        with pytest.raises(RuntimeError, match="Unknown Git hosting provider"):
            _detect_provider("https://bitbucket.org/owner/repo.git")

    def test_unparseable_url(self):
        with pytest.raises(RuntimeError, match="Cannot parse host"):
            _detect_provider("not-a-url")


class TestParseOwnerRepo:
    def test_ssh_format(self):
        owner, repo = _parse_owner_repo("git@github.com:my-org/my-repo.git")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_https_format(self):
        owner, repo = _parse_owner_repo("https://github.com/my-org/my-repo.git")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_https_no_dot_git(self):
        owner, repo = _parse_owner_repo("https://github.com/my-org/my-repo")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_unrecognized_format(self):
        with pytest.raises(RuntimeError, match="Unrecognized remote URL format"):
            _parse_owner_repo("ftp://host/owner/repo")


class TestCreatePR:
    @patch("autocommit.utils.pr_utils._run")
    def test_github_pr_created(self, mock_run):
        """Verify create_pr calls PyGithub's create_pull with correct args."""
        mock_run.return_value = (0, "git@github.com:my-org/my-repo.git", "")

        mock_github_instance = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/my-org/my-repo/pull/42"
        mock_repo.create_pull.return_value = mock_pr
        mock_github_instance.get_repo.return_value = mock_repo

        # Patch github.Github (the class imported inside create_pr)
        with patch("github.Github", return_value=mock_github_instance) as mock_github_class:
            url = create_pr(
                repo_path="/fake/path",
                token="ghp_fake_token",
                head_branch="feature-xyz",
                base_branch="main",
                title="feat: add feature",
                body="Closes #123",
            )

        assert url == "https://github.com/my-org/my-repo/pull/42"
        mock_github_class.assert_called_once_with("ghp_fake_token")
        mock_github_instance.get_repo.assert_called_once_with("my-org/my-repo")
        mock_repo.create_pull.assert_called_once_with(
            title="feat: add feature",
            body="Closes #123",
            base="main",
            head="feature-xyz",
        )

    @patch("autocommit.utils.pr_utils._run")
    def test_gitlab_mr_created(self, mock_run):
        """Verify create_pr calls python-gitlab's mergerequests.create."""
        mock_run.return_value = (0, "git@gitlab.com:my-org/my-repo.git", "")

        mock_gitlab_instance = MagicMock()
        mock_project = MagicMock()
        mock_mr = MagicMock()
        mock_mr.web_url = "https://gitlab.com/my-org/my-repo/-/merge_requests/7"
        mock_project.mergerequests.create.return_value = mock_mr
        mock_gitlab_instance.projects.get.return_value = mock_project

        # Patch gitlab.Gitlab (the class imported inside create_pr)
        with patch("gitlab.Gitlab", return_value=mock_gitlab_instance) as mock_gitlab_class:
            url = create_pr(
                repo_path="/fake/path",
                token="glpat_fake_token",
                head_branch="feature-xyz",
                base_branch="main",
                title="feat: add feature",
            )

        assert url == "https://gitlab.com/my-org/my-repo/-/merge_requests/7"
        mock_gitlab_class.assert_called_once_with(private_token="glpat_fake_token")
        mock_gitlab_instance.projects.get.assert_called_once_with("my-org/my-repo")
        mock_project.mergerequests.create.assert_called_once_with(
            {
                "source_branch": "feature-xyz",
                "target_branch": "main",
                "title": "feat: add feature",
                "description": "",
            }
        )

    @patch("autocommit.utils.pr_utils._run")
    def test_github_library_missing(self, mock_run):
        """RuntimeError raised when PyGithub not installed."""
        mock_run.return_value = (0, "git@github.com:owner/repo.git", "")

        with patch.dict(sys.modules, {"github": None}):
            with pytest.raises(RuntimeError, match="PyGithub is required"):
                create_pr(
                    repo_path="/fake/path",
                    token="fake",
                    head_branch="feature",
                    base_branch="main",
                    title="test",
                )

    @patch("autocommit.utils.pr_utils._run")
    def test_gitlab_library_missing(self, mock_run):
        """RuntimeError raised when python-gitlab not installed."""
        mock_run.return_value = (0, "git@gitlab.com:owner/repo.git", "")

        with patch.dict(sys.modules, {"gitlab": None}):
            with pytest.raises(RuntimeError, match="python-gitlab is required"):
                create_pr(
                    repo_path="/fake/path",
                    token="fake",
                    head_branch="feature",
                    base_branch="main",
                    title="test",
                )

    @patch("autocommit.utils.pr_utils._run")
    def test_missing_origin_remote(self, mock_run):
        """RuntimeError raised when git remote get-url origin fails."""
        mock_run.return_value = (128, "", "fatal: not a git repository")

        with pytest.raises(RuntimeError, match="Cannot get remote origin URL"):
            create_pr(
                repo_path="/fake/path",
                token="fake",
                head_branch="feature",
                base_branch="main",
                title="test",
            )


class TestCreatePRAndAutoMerge:
    """Tests for create_pr_and_auto_merge()."""

    @patch("autocommit.utils.pr_utils._run")
    def test_github_auto_merge_enabled(self, mock_run):
        """GitHub: auto_merge=True calls enable_auto_merge with correct method."""
        mock_run.return_value = (0, "git@github.com:my-org/my-repo.git", "")

        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/my-org/my-repo/pull/42"
        mock_repo.create_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo

        with patch("github.Github", return_value=mock_github):
            url = create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="ghp_token",
                head_branch="feature-xyz",
                base_branch="main",
                title="feat: add feature",
                body="Closes #123",
                auto_merge=True,
                merge_method="squash",
            )

        assert url == "https://github.com/my-org/my-repo/pull/42"
        mock_pr.enable_auto_merge.assert_called_once_with(merge_method="SQUASH")

    @patch("autocommit.utils.pr_utils._run")
    def test_github_auto_merge_default_method(self, mock_run):
        """GitHub: default merge_method is 'merge' -> MERGE."""
        mock_run.return_value = (0, "git@github.com:my-org/my-repo.git", "")

        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/my-org/my-repo/pull/1"
        mock_repo.create_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo

        with patch("github.Github", return_value=mock_github):
            url = create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="ghp_token",
                head_branch="feature",
                base_branch="main",
                title="test",
                auto_merge=True,
            )

        assert url == "https://github.com/my-org/my-repo/pull/1"
        mock_pr.enable_auto_merge.assert_called_once_with(merge_method="MERGE")

    @patch("autocommit.utils.pr_utils._run")
    def test_github_auto_merge_disabled(self, mock_run):
        """GitHub: auto_merge=False does NOT call enable_auto_merge."""
        mock_run.return_value = (0, "git@github.com:my-org/my-repo.git", "")

        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/my-org/my-repo/pull/1"
        mock_repo.create_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo

        with patch("github.Github", return_value=mock_github):
            url = create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="ghp_token",
                head_branch="feature",
                base_branch="main",
                title="test",
                auto_merge=False,
            )

        assert url == "https://github.com/my-org/my-repo/pull/1"
        mock_pr.enable_auto_merge.assert_not_called()

    @patch("autocommit.utils.pr_utils._run")
    def test_gitlab_auto_merge_enabled(self, mock_run):
        """GitLab: auto_merge=True sets merge_when_pipeline_succeeds and saves."""
        mock_run.return_value = (0, "git@gitlab.com:my-org/my-repo.git", "")

        mock_gitlab = MagicMock()
        mock_project = MagicMock()
        mock_mr = MagicMock()
        mock_mr.web_url = "https://gitlab.com/my-org/my-repo/-/merge_requests/7"
        mock_project.mergerequests.create.return_value = mock_mr
        mock_gitlab.projects.get.return_value = mock_project

        with patch("gitlab.Gitlab", return_value=mock_gitlab):
            url = create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="glpat_token",
                head_branch="feature",
                base_branch="main",
                title="feat: add feature",
                auto_merge=True,
                merge_method="merge",
            )

        assert url == "https://gitlab.com/my-org/my-repo/-/merge_requests/7"
        assert mock_mr.merge_when_pipeline_succeeds is True
        mock_mr.save.assert_called_once()

    @patch("autocommit.utils.pr_utils._run")
    def test_gitlab_auto_merge_disabled(self, mock_run):
        """GitLab: auto_merge=False does not call save (no auto-merge)."""
        mock_run.return_value = (0, "git@gitlab.com:my-org/my-repo.git", "")

        mock_gitlab = MagicMock()
        mock_project = MagicMock()
        mock_mr = MagicMock()
        mock_mr.web_url = "https://gitlab.com/my-org/my-repo/-/merge_requests/8"
        mock_project.mergerequests.create.return_value = mock_mr
        mock_gitlab.projects.get.return_value = mock_project

        with patch("gitlab.Gitlab", return_value=mock_gitlab):
            url = create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="glpat_token",
                head_branch="feature",
                base_branch="main",
                title="test",
                auto_merge=False,
            )

        assert url == "https://gitlab.com/my-org/my-repo/-/merge_requests/8"
        # save() is only called when auto_merge=True triggers _enable_gitlab_auto_merge
        mock_mr.save.assert_not_called()

    @patch("autocommit.utils.pr_utils._run")
    def test_invalid_merge_method_raises(self, mock_run):
        """Invalid merge_method raises RuntimeError before any API call."""
        with pytest.raises(RuntimeError, match="Invalid merge_method"):
            create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="token",
                head_branch="feature",
                base_branch="main",
                title="test",
                auto_merge=True,
                merge_method="invalid",
            )
        # _run should not have been called (error is raised before remote URL fetch)
        mock_run.assert_not_called()

    @patch("autocommit.utils.pr_utils._run")
    def test_auto_merge_unsupported_provider(self, mock_run):
        """Auto-merge on unknown provider raises RuntimeError."""
        mock_run.return_value = (0, "git@bitbucket.org:owner/repo.git", "")

        with pytest.raises(RuntimeError, match="Unknown Git hosting provider"):
            create_pr_and_auto_merge(
                repo_path="/fake/path",
                token="token",
                head_branch="feature",
                base_branch="main",
                title="test",
                auto_merge=True,
            )

    @patch("autocommit.utils.pr_utils._run")
    def test_github_auto_merge_old_library(self, mock_run):
        """Old PyGithub without enable_auto_merge raises RuntimeError."""
        mock_run.return_value = (0, "git@github.com:owner/repo.git", "")

        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/owner/repo/pull/1"
        # Simulate old library: no enable_auto_merge method
        del mock_pr.enable_auto_merge
        mock_repo.create_pull.return_value = mock_pr
        mock_github.get_repo.return_value = mock_repo

        with patch("github.Github", return_value=mock_github):
            with pytest.raises(RuntimeError, match="does not support enable_auto_merge"):
                create_pr_and_auto_merge(
                    repo_path="/fake/path",
                    token="token",
                    head_branch="feature",
                    base_branch="main",
                    title="test",
                    auto_merge=True,
                )
