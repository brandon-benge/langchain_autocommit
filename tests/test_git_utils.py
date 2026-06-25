import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from autocommit.utils.git_utils import (
    autostage_all,
    changed_files,
    commit,
    current_branch,
    ensure_git_repo,
    find_ticket,
    infer_scope_from_cwd,
    infer_type_from_paths,
    push,
    staged_diff_summary,
)


class TestEnsureGitRepo:
    def test_inside_repo(self, temp_git_repo):
        ensure_git_repo(temp_git_repo)

    def test_not_a_repo(self, tmp_path):
        with pytest.raises(RuntimeError):
            ensure_git_repo(str(tmp_path))


class TestCurrentBranch:
    def test_returns_string(self, temp_git_repo):
        branch = current_branch(temp_git_repo)
        assert isinstance(branch, str)
        assert len(branch) > 0


class TestChangedFiles:
    def test_initial_state_no_changes(self, temp_git_repo):
        files = changed_files(temp_git_repo)
        assert isinstance(files, list)
        assert len(files) == 0

    def test_staged_and_unstaged(self, temp_git_repo):
        test_file = os.path.join(temp_git_repo, "new_file.py")
        with open(test_file, "w") as f:
            f.write("# test")
        files = changed_files(temp_git_repo)
        assert "new_file.py" in files


class TestStagedDiffSummary:
    def test_returns_string(self, temp_git_repo):
        result = staged_diff_summary(temp_git_repo)
        assert isinstance(result, str)

    def test_includes_patch_when_enabled(self, repo_with_staged_changes):
        result = staged_diff_summary(repo_with_staged_changes, include_patch=True)
        assert "---PATCH---" in result
        assert "def hello" in result

    def test_omits_patch_when_disabled(self, repo_with_staged_changes):
        result = staged_diff_summary(repo_with_staged_changes, include_patch=False)
        assert "---PATCH---" not in result


class TestCommit:
    def test_commits_successfully(self, temp_git_repo):
        test_file = os.path.join(temp_git_repo, "commit_test.py")
        with open(test_file, "w") as f:
            f.write("# test commit")
        autostage_all(temp_git_repo)
        commit(temp_git_repo, "test: subject", "test body")
        files = changed_files(temp_git_repo)
        assert len(files) == 0

    def test_amend_flag(self, temp_git_repo):
        commit(temp_git_repo, "test: amended", "amended body", amend=True)


class TestPush:
    def test_push_call(self, mocker, temp_git_repo):
        mock_run = mocker.patch("autocommit.utils.git_utils._run", return_value=(0, "", ""))
        push(temp_git_repo)
        assert any("git push" in call_args[0][0] for call_args in mock_run.call_args_list)


class TestInferTypeFromPaths:
    def test_test_files(self):
        assert infer_type_from_paths(["tests/test_a.py", "tests/test_b.py"]) == "test"

    def test_docs_files(self):
        assert infer_type_from_paths(["docs/guide.md", "src/main.py"]) == "docs"

    def test_scripts(self):
        assert infer_type_from_paths(["scripts/deploy.sh"]) == "chore"

    def test_default_feat(self):
        assert infer_type_from_paths(["src/main.py", "src/utils.py"]) == "feat"

    def test_empty_list(self):
        assert infer_type_from_paths([]) == "feat"

    def test_js_test_files(self):
        assert infer_type_from_paths(["__tests__/button.test.js", "__tests__/nav.spec.ts"]) == "test"

    def test_ci_config_files(self):
        assert infer_type_from_paths([".github/workflows/ci.yml"]) == "chore"

    def test_docker_config(self):
        assert infer_type_from_paths(["docker/Dockerfile"]) == "chore"

    def test_config_files(self):
        assert infer_type_from_paths(["config/deploy.yml"]) == "chore"

    def test_fix_path(self):
        assert infer_type_from_paths(["fix/login-error.py"]) == "fix"

    def test_hotfix_path(self):
        assert infer_type_from_paths(["hotfix/crash-handler.py"]) == "fix"

    def test_mixed_test_and_src(self):
        assert infer_type_from_paths(["tests/test_a.py", "src/main.py"]) != "test"

    def test_api_routes(self):
        assert infer_type_from_paths(["api/routes.py"]) == "feat"

    def test_app_models(self):
        assert infer_type_from_paths(["app/models/user.py"]) == "feat"

    def test_components(self):
        assert infer_type_from_paths(["ui/components/Button.tsx"]) == "feat"


class TestInferScope:
    def test_returns_basename(self, temp_git_repo):
        scope = infer_scope_from_cwd(temp_git_repo)
        assert "test_repo" in scope


class TestFindTicket:
    def test_extracts_ticket(self):
        ticket = find_ticket("feat/PROJ-123-add-auth", r"[A-Z]{2,}-\d+")
        assert ticket == "PROJ-123"

    def test_no_match_returns_empty(self):
        ticket = find_ticket("main", r"[A-Z]{2,}-\d+")
        assert ticket == ""

    def test_custom_pattern(self):
        ticket = find_ticket("fix/ISSUE-42", r"ISSUE-\d+")
        assert ticket == "ISSUE-42"
