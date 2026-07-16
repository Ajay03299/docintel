from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def load_rule_config(path: str | Path) -> dict[str, Any]:
    """Load per-rule config: {rule_id: {enabled, severity, params}}."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Validation config not found: {p}")
    data = yaml.safe_load(p.read_text()) or {}
    return data.get("rules", {})


@lru_cache
def invoice_rule_config() -> dict[str, Any]:
    return load_rule_config(Path(__file__).parents[2] / "plugins" / "invoice" / "validation.yaml")
