"""Central config loader. No thresholds/paths should be hardcoded elsewhere in src/."""
from __future__ import annotations
import functools
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "thresholds.yaml"


@functools.lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def data_path(key: str) -> Path:
    cfg = load_config()
    rel = cfg["data_sources"][key]["path"] if isinstance(cfg["data_sources"][key], dict) else cfg["data_sources"][key]
    return REPO_ROOT / rel


def source_version(key: str) -> str | None:
    cfg = load_config()
    entry = cfg["data_sources"][key]
    return entry.get("version_column") if isinstance(entry, dict) else None
