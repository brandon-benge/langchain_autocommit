import os

from scripts.git_utils import (
    infer_type_from_paths,
    infer_scope_from_cwd,
    find_ticket,
    ensure_git_repo,
    current_branch,
    changed_files,
    autostage_all,
)


class TestInferTypeFromPaths:
    def test_test_type(self):
        assert infer_type_from_paths(["tests/test_a.py", "tests/test_b.py"]) == "test"

    def test_test_type_single_test_file(self):
        assert infer_type_from_paths(["src/module_test.py"]) == "test"

    def test_docs_type(self):
        assert infer_type_from_paths(["docs/guide.md"]) == "docs"

    def test_docs_type_markdown_file(self):
        assert infer_type_from_paths(["README.md"]) == "docs"

    def test_chore_type_scripts(self):
        assert infer_type_from_paths(["scripts/deploy.sh"]) == "chore"

    def test_chore_type_github(self):
        assert infer_type_from_paths([".github/workflows/ci.yml"]) == "chore"

    def test_feat_default(self):
        assert infer_type_from_paths(["src/main.py"]) == "feat"

    def test_feat_mixed(self):
        assert infer_type_from_paths(["src/main.py", "tests/test_a.py"]) == "feat"

    def test_empty_paths(self):
        assert infer_type_from_paths([]) == "test"


class TestFindTicket:
    def test_finds_ticket(self):
        assert find_ticket("feat/PROJ-123-add-auth", r"[A-Z]{2,}-\d+") == "PROJ-123"

    def test_no_match(self):
        assert find_ticket("main", r"[A-Z]{2,}-\d+") == ""

    def test_multiple_tickets(self):
        assert find_ticket("feature/ABC-1/DEF-2-fix", r"[A-Z]{2,}-\d+") == "ABC-1"

    def test_lowercase_prefix(self):
        assert find_ticket("fix/ab-1-foo", r"[A-Z]{2,}-\d+") == ""


class TestInferScopeFromCwd:
    def test_returns_basename(self, tmp_path):
        subdir = tmp_path / "my_project"
        subdir.mkdir()
        assert infer_scope_from_cwd(str(subdir)) == "my_project"

    def test_root_dir(self):
        assert infer_scope_from_cwd("/") == ""


class TestGitUtilsIntegration:
    def test_ensure_git_repo(self, temp_git_repo):
        ensure_git_repo(temp_git_repo)

    def test_ensure_git_repo_raises(self, tmp_path):
        import pytest
        with pytest.raises(RuntimeError, match="Not a git repository"):
            ensure_git_repo(str(tmp_path))

    def test_current_branch(self, temp_git_repo):
        assert current_branch(temp_git_repo) == "main"

    def test_changed_files_empty(self, temp_git_repo):
        assert changed_files(temp_git_repo) == []

    def test_changed_files_detects_modification(self, temp_git_repo):
        repo_path = temp_git_repo
        with open(os.path.join(repo_path, "readme.md"), "a") as f:
            f.write("\nmore content")
        files = changed_files(repo_path)
        assert len(files) == 1

    def test_autostage_all(self, temp_git_repo):
        repo_path = temp_git_repo
        unstaged_file = os.path.join(repo_path, "new_file.py")
        with open(unstaged_file, "w") as f:
            f.write("x = 1")
        autostage_all(repo_path)
        files = changed_files(repo_path)
        assert "new_file.py" in files
