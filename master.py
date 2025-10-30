#!/usr/bin/env python3
"""
master.py - Config and utility loader for LangChain AutoCommit
"""
import os

def parse_yaml_simple(path: str) -> dict:
    data = {}
    stack = [data]
    indent_levels = [0]

    def set_kv(container, key, value):
        v = value.strip()
        # Remove inline comments (everything after #)
        if '#' in v:
            v = v.split('#')[0].strip()
        # Remove quotes if present
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        # Convert string representations of booleans and numbers
        if v.lower() in ('true', 'false'):
            container[key] = v.lower() == 'true'
        elif v.isdigit():
            container[key] = int(v)
        elif v.replace('.', '', 1).isdigit() and v.count('.') <= 1:
            container[key] = float(v)
        else:
            container[key] = v

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.strip().startswith("#"):
                continue
            sp = len(line) - len(line.lstrip(" "))
            while sp < indent_levels[-1]:
                stack.pop(); indent_levels.pop()
            if ":" in line:
                key, val = line.strip().split(":", 1)
                if not val.strip():
                    new_map = {}
                    stack[-1][key.strip()] = new_map
                    stack.append(new_map); indent_levels.append(sp + 2)
                else:
                    set_kv(stack[-1], key.strip(), val.strip())
    return data

def load_config() -> dict:
    root = os.path.dirname(os.path.abspath(__file__))
    return parse_yaml_simple(os.path.join(root, "params.yaml"))
