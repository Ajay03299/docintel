from app.engines.validation.base import ValidationRule

_RULES: dict[str, type[ValidationRule]] = {}
_LOADED = False


def register_rule(cls: type[ValidationRule]) -> type[ValidationRule]:
    """Decorator: a rule class registers itself at import time.

    Adding a rule requires editing NO existing file — the engine never grows an
    if/elif chain and no central list needs updating (Open/Closed Principle).
    """
    if not getattr(cls, "rule_id", ""):
        raise ValueError(f"{cls.__name__} must define a non-empty rule_id")
    if cls.rule_id in _RULES:
        raise ValueError(
            f"duplicate rule_id {cls.rule_id!r}: {cls.__name__} vs "
            f"{_RULES[cls.rule_id].__name__}"
        )
    _RULES[cls.rule_id] = cls
    return cls


def _ensure_loaded() -> None:
    """Import the rules package so decorators fire.

    The registry loads rules itself rather than relying on callers to import the
    package first: a get_rules() that silently returns {} because of import
    ordering is a contract the caller cannot see it has broken.
    """
    global _LOADED
    if _LOADED:
        return
    _LOADED = True  # set first: a rule module calling get_rules() must not recurse
    import app.engines.validation.rules  # noqa: F401  (triggers @register_rule)


def get_rules() -> dict[str, type[ValidationRule]]:
    _ensure_loaded()
    return dict(_RULES)


def clear_rules() -> None:
    """Test-only helper."""
    global _LOADED
    _RULES.clear()
    _LOADED = False
