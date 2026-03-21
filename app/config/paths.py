from pathlib import Path


class Paths:

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir).resolve() if base_dir is not None else None

    @property
    def base_dir(self) -> Path:
        """Root directory for all application data."""
        if self._base_dir is not None:
            return self._base_dir

        cwd = Path.cwd()
        if cwd.name == "smallclaw" or (cwd / "pyproject.toml").exists():
            return cwd / ".small-claw"

        return Path.home() / ".small-claw"


_paths: Paths | None = None


def get_paths() -> Paths:
    """Return the global Paths singleton (lazy-initialized)."""
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths
