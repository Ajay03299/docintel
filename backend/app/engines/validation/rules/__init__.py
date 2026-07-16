"""Rule package with filesystem autoloading.

Every module in this directory is imported on package import, which triggers the
@register_rule decorators. Consequence: dropping a new .py file in this folder
makes the rule live — no imports to add, no lists to update, no engine edits.
That is the literal meaning of "extensible without modifying existing code".
"""

import importlib
import pkgutil
from pathlib import Path


def _autoload() -> None:
    for module in pkgutil.iter_modules([str(Path(__file__).parent)]):
        importlib.import_module(f"{__name__}.{module.name}")


_autoload()
