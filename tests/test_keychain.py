from unittest.mock import patch

from autocommit.utils.keychain import get_api_key, set_api_key


class TestGetApiKey:
    def test_returns_value_from_keyring(self, mocker):
        mock_get = mocker.patch("keyring.get_password", return_value="sk-abc123")
        result = get_api_key("my_service", "my_key")
        mock_get.assert_called_once_with("my_service", "my_key")
        assert result == "sk-abc123"

    def test_returns_none_when_keyring_returns_none(self, mocker):
        mocker.patch("keyring.get_password", return_value=None)
        result = get_api_key("svc", "key")
        assert result is None


class TestSetApiKey:
    def test_stores_value_in_keyring(self, mocker):
        mock_set = mocker.patch("keyring.set_password")
        set_api_key("my_service", "my_key", "sk-secret")
        mock_set.assert_called_once_with("my_service", "my_key", "sk-secret")
