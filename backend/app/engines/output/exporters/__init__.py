"""Exporter package with filesystem autoloading (same pattern as validation rules)."""

import importlib
import pkgutil
from pathlib import Path


def _autoload() -> None:
    for module in pkgutil.iter_modules([str(Path(__file__).parent)]):
        importlib.import_module(f"{__name__}.{module.name}")


_autoload()
