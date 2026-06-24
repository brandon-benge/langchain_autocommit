from scripts.keychain import get_api_key, set_api_key


class TestGetApiKey:
    def test_returns_password(self, mocker):
        mocker.patch("keyring.get_password", return_value="sk-test-key")
        result = get_api_key("myservice", "mykey")
        assert result == "sk-test-key"

    def test_returns_none_when_missing(self, mocker):
        mocker.patch("keyring.get_password", return_value=None)
        result = get_api_key("myservice", "mykey")
        assert result is None

    def test_passes_correct_args(self, mocker):
        mock = mocker.patch("keyring.get_password", return_value="k")
        get_api_key("langchain_autocommit", "opencode_api_key")
        mock.assert_called_once_with("langchain_autocommit", "opencode_api_key")


class TestSetApiKey:
    def test_stores_password(self, mocker):
        mock = mocker.patch("keyring.set_password")
        set_api_key("myservice", "mykey", "sk-new-key")
        mock.assert_called_once_with("myservice", "mykey", "sk-new-key")
