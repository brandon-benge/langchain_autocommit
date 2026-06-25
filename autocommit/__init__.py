from autocommit.core import CommitMessage, apply_commit, generate_and_commit, generate_commit_message
from autocommit.config import DEFAULT_CONFIG, deep_merge, load_config

__all__ = [
    "generate_commit_message",
    "apply_commit",
    "generate_and_commit",
    "CommitMessage",
    "load_config",
    "DEFAULT_CONFIG",
    "deep_merge",
]
