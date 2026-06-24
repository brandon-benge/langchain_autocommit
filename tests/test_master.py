import os, tempfile

import yaml
from master import load_config


def test_load_config_returns_dict():
    cfg = load_config()
    assert isinstance(cfg, dict)


def test_load_config_has_expected_keys():
    cfg = load_config()
    assert "llm" in cfg
    assert "git" in cfg
    assert "paths" in cfg
    assert "project_name" in cfg


def test_load_config_llm_structure():
    cfg = load_config()
    llm = cfg["llm"]
    assert "primary" in llm
    assert "fallback" in llm
    assert "base_url" in llm["primary"]
    assert "model" in llm["primary"]
    assert "keychain" in llm["primary"]


def test_load_config_git_structure():
    cfg = load_config()
    git = cfg["git"]
    assert "autostage_all" in git
    assert "conventional" in git
    assert "max_subject_length" in git

