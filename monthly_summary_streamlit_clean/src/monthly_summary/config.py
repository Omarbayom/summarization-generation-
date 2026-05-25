from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

# Loads user's normal .env from the current working directory/project folder.
load_dotenv()

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default = match.group(2) or ""
            return os.getenv(var_name, default)
        previous = None
        current = value
        for _ in range(5):
            if current == previous:
                break
            previous = current
            current = _ENV_PATTERN.sub(replace, current)
        return current
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


DEFAULT_CONFIG: Dict[str, Any] = {
    "project": {
        "name": "monthly-summary-generator",
        "output_dir": "outputs",
        "default_year": 2026,
    },
    "excel": {
        "header_scan_rows": 100,
        "category_header": "Category",
        "start_marker": "Date:",
        "end_markers": ["SYS Engineering:", "SYS Engineering"],
        "blockers_marker": "Blockers",
        "support_marker": "Support Needed",
        "support_clear_rows": 25,
        "empty_streak_stop": 10,
        "max_input_chars_per_team": 70000,
    },
    "llm": {
        "provider": "ollama",
        "base_url": "https://ollama.com",
        "api_key_env": "OLLAMA_API_KEY",
        "summary_model": "gpt-oss:120b-cloud",
        "bigger_summary_model": "gpt-oss:120b-cloud",
        "fallback_models": ["gemma4:31b-cloud", "gemma4:26b", "gpt-oss:20b-cloud"],
        "temperature": 0.05,
        "top_p": 0.9,
        "num_ctx": 128000,
        "summary_max_tokens": 2500,
        "bigger_summary_max_tokens": 5500,
        "request_timeout_seconds": 900,
        "retry_count": 2,
        "request_sleep_seconds": 0.5,
        "reasoning_effort": "high",
        "json_mode": True,
    },
    "pdf": {
        "summary_title": "Executive Summary Report",
        "bigger_summary_title": "Detailed Summary Report",
        "one_team_per_page": False,
        "font_family": "times",
    },
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "email_from": "",
        "email_to": "",
        "subject": "Monthly Summary Reports",
        "body": "Attached are the summary and bigger summary reports.",
    },
}


def load_config(config_path: str | Path | None = None, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    if config_path:
        path = Path(config_path)
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                file_cfg = yaml.safe_load(f) or {}
            cfg = deep_merge(cfg, file_cfg)
    cfg = deep_merge(cfg, overrides or {})
    return _expand_env(cfg)


def output_dir_from_config(cfg: Dict[str, Any]) -> Path:
    out = Path(cfg.get("project", {}).get("output_dir", "outputs"))
    out.mkdir(parents=True, exist_ok=True)
    return out
