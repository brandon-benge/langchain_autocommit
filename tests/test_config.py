import importlib

import pytest
import yaml

import autocommit.config as config_module
from autocommit.config import deep_merge, load_config


class TestDeepMerge:
    def test_overrides_replaces_scalar(self):
        base = {"key": "old"}
        overrides = {"key": "new"}
        result = deep_merge(base, overrides)
        assert result == {"key": "new"}

    def test_overrides_merges_nested_dicts(self):
        base = {"llm": {"primary": {"model": "gpt-4", "temperature": 0.2}}}
        overrides = {"llm": {"primary": {"temperature": 0.5}}}
        result = deep_merge(base, overrides)
        assert result["llm"]["primary"]["model"] == "gpt-4"
        assert result["llm"]["primary"]["temperature"] == 0.5

    def test_overrides_adds_new_keys(self):
        base = {"llm": {}}
        overrides = {"git": {"autostage_all": True}}
        result = deep_merge(base, overrides)
        assert result["git"]["autostage_all"] is True

    def test_overrides_replaces_dict_with_scalar(self):
        base = {"git": {"quality": {"max_retries": 2}}}
        overrides = {"git": "disabled"}
        result = deep_merge(base, overrides)
        assert result["git"] == "disabled"

    def test_original_base_not_mutated(self):
        base = {"key": {"nested": "value"}}
        original_base = {"key": {"nested": "value"}}
        overrides = {"key": {"nested": "changed"}}
        deep_merge(base, overrides)
        assert base == original_base


class TestLoadConfigWithConfigPath:
    def test_custom_file_loads_successfully(self, tmp_path):
        custom_cfg = {
            "project_name": "Custom Project",
            "llm": {"primary": {"model": "custom-model", "temperature": 0.5}},
            "git": {"autostage_all": False},
            "paths": {"logs_dir": "custom_logs"},
        }
        config_file = tmp_path / "custom.yaml"
        with open(config_file, "w") as f:
            yaml.dump(custom_cfg, f)

        result = load_config(config_path=str(config_file))
        assert result["project_name"] == "Custom Project"
        assert result["llm"]["primary"]["model"] == "custom-model"
        assert result["git"]["autostage_all"] is False

    def test_custom_file_not_found_raises_file_not_found_error(self):
        with pytest.raises(FileNotFoundError):
            load_config(config_path="/nonexistent/path/config.yaml")

    def test_custom_file_bad_yaml_raises_yaml_error(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{invalid: yaml: broken: [[[")

        with pytest.raises(yaml.YAMLError):
            load_config(config_path=str(bad_file))

    def test_overrides_on_top_of_custom_file(self, tmp_path):
        custom_cfg = {
            "llm": {"primary": {"model": "base-model", "temperature": 0.2}},
            "git": {"autostage_all": False},
        }
        config_file = tmp_path / "custom.yaml"
        with open(config_file, "w") as f:
            yaml.dump(custom_cfg, f)

        overrides = {"llm": {"primary": {"temperature": 0.7}}, "git": {"autostage_all": True}}
        result = load_config(config_path=str(config_file), overrides=overrides)

        # Custom file values (not overridden) survive
        assert result["llm"]["primary"]["model"] == "base-model"
        # Overridden values win
        assert result["llm"]["primary"]["temperature"] == 0.7
        assert result["git"]["autostage_all"] is True

    def test_default_no_args_still_loads_bundled(self, monkeypatch):
        """Backward compatibility: load_config() with no args loads the bundled params.yaml."""
        monkeypatch.delenv("AUTOCOMMIT_PARAMS", raising=False)
        result = load_config()
        assert "project_name" in result
        assert "llm" in result
        assert "git" in result
        assert "paths" in result
        # Verify it's the bundled file by checking known defaults
        assert result["project_name"] == "LangChain AutoCommit"
        assert result["python_version"] == "3.10"

    def test_overrides_work_without_config_path(self, monkeypatch):
        """Backward compatibility: load_config(overrides=...) still works."""
        monkeypatch.delenv("AUTOCOMMIT_PARAMS", raising=False)
        overrides = {"git": {"autostage_all": False}}
        result = load_config(overrides=overrides)
        assert result["git"]["autostage_all"] is False
        # Other keys from bundled file survive
        assert result["llm"]["primary"]["model"] == "deepseek-v4-flash-free"


class TestLoadConfigWithAutoCommitParamsEnvVar:
    ENV_VAR = "AUTOCOMMIT_PARAMS"

    def test_env_var_used_when_no_config_path(self, tmp_path, monkeypatch):
        custom_cfg = {
            "project_name": "Environment Project",
            "llm": {"primary": {"model": "env-model"}},
            "git": {"autostage_all": False},
        }
        config_file = tmp_path / "team-config.yaml"
        config_file.write_text(yaml.safe_dump(custom_cfg))

        monkeypatch.setenv(self.ENV_VAR, str(config_file))

        assert load_config() == custom_cfg

    def test_explicit_config_path_overrides_invalid_env_var(self, tmp_path, monkeypatch):
        explicit_cfg = {"project_name": "Explicit Project"}
        explicit_file = tmp_path / "explicit.yaml"
        explicit_file.write_text(yaml.safe_dump(explicit_cfg))
        monkeypatch.setenv(self.ENV_VAR, str(tmp_path / "missing-env.yaml"))

        result = load_config(config_path=str(explicit_file))

        assert result == explicit_cfg

    @pytest.mark.parametrize("env_value", [None, ""])
    def test_unset_or_empty_env_var_uses_bundled(self, env_value, monkeypatch):
        if env_value is None:
            monkeypatch.delenv(self.ENV_VAR, raising=False)
        else:
            monkeypatch.setenv(self.ENV_VAR, env_value)

        result = load_config()

        assert result["project_name"] == "LangChain AutoCommit"
        assert result["python_version"] == "3.10"

    def test_relative_env_var_path_with_arbitrary_filename(self, tmp_path, monkeypatch):
        custom_cfg = {"project_name": "Relative Environment Project"}
        config_file = tmp_path / "my-settings.yaml"
        config_file.write_text(yaml.safe_dump(custom_cfg))
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(self.ENV_VAR, config_file.name)

        assert load_config() == custom_cfg

    def test_missing_env_var_file_raises_file_not_found_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv(self.ENV_VAR, str(tmp_path / "missing.yaml"))

        with pytest.raises(FileNotFoundError):
            load_config()

    def test_malformed_env_var_file_raises_yaml_error(self, tmp_path, monkeypatch):
        config_file = tmp_path / "malformed.yaml"
        config_file.write_text("{invalid: yaml: broken: [[[")
        monkeypatch.setenv(self.ENV_VAR, str(config_file))

        with pytest.raises(yaml.YAMLError):
            load_config()

    def test_overrides_merge_on_top_of_env_var_file(self, tmp_path, monkeypatch):
        custom_cfg = {
            "llm": {"primary": {"model": "env-model", "temperature": 0.2}},
            "git": {"autostage_all": False},
        }
        config_file = tmp_path / "environment.yaml"
        config_file.write_text(yaml.safe_dump(custom_cfg))
        monkeypatch.setenv(self.ENV_VAR, str(config_file))

        result = load_config(
            overrides={"llm": {"primary": {"temperature": 0.7}}}
        )

        assert result["llm"]["primary"] == {
            "model": "env-model",
            "temperature": 0.7,
        }
        assert result["git"]["autostage_all"] is False

    def test_default_config_remains_bundled_when_module_reloads(self, tmp_path, monkeypatch):
        custom_cfg = {"project_name": "Environment Project"}
        config_file = tmp_path / "environment.yaml"
        config_file.write_text(yaml.safe_dump(custom_cfg))
        monkeypatch.setenv(self.ENV_VAR, str(config_file))

        reloaded = importlib.reload(config_module)

        assert reloaded.DEFAULT_CONFIG["project_name"] == "LangChain AutoCommit"
        assert reloaded.DEFAULT_CONFIG["python_version"] == "3.10"
        assert reloaded.load_config() == custom_cfg
