import os
import tempfile

import yaml
from autocommit.config import load_config


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
    assert "env_var" in llm["primary"]


def test_load_config_git_structure():
    cfg = load_config()
    git = cfg["git"]
    assert "autostage_all" in git
    assert "conventional" in git
    assert "max_subject_length" in git


def test_deep_merge():
    from autocommit.config import deep_merge
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    overrides = {"b": {"c": 99}, "e": 4}
    result = deep_merge(base, overrides)
    assert result["a"] == 1
    assert result["b"]["c"] == 99
    assert result["b"]["d"] == 3
    assert result["e"] == 4


def test_load_config_with_overrides():
    cfg = load_config(overrides={"git": {"max_subject_length": 999}})
    assert cfg["git"]["max_subject_length"] == 999
    assert "llm" in cfg
