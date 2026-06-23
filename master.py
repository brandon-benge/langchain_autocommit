#!/usr/bin/env python3
"""
master.py - Config loader for LangChain AutoCommit
"""
import os
import yaml


def load_config() -> dict:
    root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(root, "params.yaml"), "r") as f:
        return yaml.safe_load(f)
