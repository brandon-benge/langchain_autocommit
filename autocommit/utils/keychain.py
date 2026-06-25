import keyring


def get_api_key(service: str, key: str) -> str | None:
    return keyring.get_password(service, key)


def set_api_key(service: str, key: str, value: str) -> None:
    keyring.set_password(service, key, value)
