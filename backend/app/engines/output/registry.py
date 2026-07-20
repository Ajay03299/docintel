from app.engines.output.base import Exporter

_EXPORTERS: dict[str, type[Exporter]] = {}
_LOADED = False


def register_exporter(cls: type[Exporter]) -> type[Exporter]:
    """Adding an output format = adding one file to exporters/. No edits here."""
    if not getattr(cls, "format_id", ""):
        raise ValueError(f"{cls.__name__} must define a non-empty format_id")
    if cls.format_id in _EXPORTERS:
        raise ValueError(f"duplicate format_id {cls.format_id!r}")
    _EXPORTERS[cls.format_id] = cls
    return cls


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    import app.engines.output.exporters  # noqa: F401


def get_exporters() -> dict[str, type[Exporter]]:
    _ensure_loaded()
    return dict(_EXPORTERS)


def get_exporter(format_id: str) -> Exporter:
    exporters = get_exporters()
    if format_id not in exporters:
        raise ValueError(f"Unknown export format {format_id!r}. Available: {sorted(exporters)}")
    return exporters[format_id]()
