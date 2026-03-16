from __future__ import annotations

import json
import os
from pathlib import Path

from coresearcher.config.schema import Config

CONFIG_PATH_ENV = "CORESEARCHER_CONFIG"


def default_config_path() -> Path:
    raw = os.environ.get(CONFIG_PATH_ENV, "~/.coresearcher/config.json")
    return Path(raw).expanduser()


def load_config(path: str | Path | None = None) -> Config:
    config_path = Path(path).expanduser() if path else default_config_path()
    if not config_path.exists():
        return Config()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return Config.model_validate(payload)


def save_config(config: Config, path: str | Path | None = None) -> Path:
    config_path = Path(path).expanduser() if path else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path
