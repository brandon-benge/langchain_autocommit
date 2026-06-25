import os
import subprocess
import sys
import tempfile
import shutil

import pytest
import yaml

from autocommit.config import load_config


@pytest.fixture
def temp_git_repo(tmp_path):
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    test_file = repo / "readme.md"
    test_file.write_text("# Test")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True)
    return str(repo)


@pytest.fixture
def sample_config():
    return {
        "llm": {
            "primary": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
                "max_tokens": 512,
                "timeout": 60,
                "keychain": {
                    "service": "langchain_autocommit",
                    "key": "opencode_api_key",
                },
            },
            "fallback": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        },
        "git": {
            "autostage_all": True,
            "signoff": True,
            "push_after_commit": True,
            "allow_amend": False,
            "conventional": True,
            "default_type": "chore",
            "scope_from_folder": True,
            "max_subject_length": 100,
            "ticket_regex": "[A-Z]{2,}-\\d+",
        },
        "paths": {
            "logs_dir": "logs",
            "temp_dir": "tmp",
        },
    }


@pytest.fixture
def sample_inputs():
    return {
        "type": "feat",
        "scope": "test_repo",
        "ticket": "PROJ-123",
        "changed_files": ["src/main.py", "src/utils.py"],
        "diff_summary": "A---\nM src/main.py\nM src/utils.py\n---\n 2 files changed",
        "max_subject_length": 72,
    }
