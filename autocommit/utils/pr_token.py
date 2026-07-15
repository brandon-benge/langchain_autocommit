"""PR API token resolution.

Reuses the existing env-var / macOS Keychain pattern from
:mod:`autocommit.utils.keychain`.
"""

import os
from typing import Any

from autocommit.utils.keychain import get_api_key


def resolve_pr_token(cfg: dict[str, Any]) -> str:
    """Resolve the PR API token from configuration.

    Priority
    --------
    1. Environment variable named by ``git.auto_pr.token_env_var``
       (default ``GITHUB_TOKEN``).
    2. macOS Keychain at ``git.auto_pr.keychain.service`` /
       ``git.auto_pr.keychain.key``.
    3. Raises :class:`RuntimeError` with a clear message if neither source
       is configured or contains a value.

    Parameters
    ----------
    cfg : dict
        The project configuration dict (as returned by
        :func:`autocommit.config.load_config`).

    Returns
    -------
    str
        The resolved API token.
    """
    auto_pr_cfg = cfg.get("git", {}).get("auto_pr", {})
    if not auto_pr_cfg:
        raise RuntimeError(
            "git.auto_pr is not configured in params.yaml. "
            "Set git.auto_pr.enabled: true and provide a token."
        )

    # 1. Environment variable
    env_var = auto_pr_cfg.get("token_env_var", "GITHUB_TOKEN")
    token = os.environ.get(env_var)
    if token:
        return token

    # 2. macOS Keychain
    kc = auto_pr_cfg.get("keychain")
    if isinstance(kc, dict):
        service = kc.get("service", "langchain_autocommit")
        key = kc.get("key", "github_token")
        token = get_api_key(service, key)
        if token:
            return token

    # 3. Neither source produced a token
    raise RuntimeError(
        f"No PR API token found. "
        f"Set environment variable {env_var} "
        f"or configure git.auto_pr.keychain in params.yaml."
    )
