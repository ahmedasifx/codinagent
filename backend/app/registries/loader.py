"""Folder-convention discovery: import every module under tools/, skills/, agents/
so their `register_*` decorators populate the registries. Call `load_builtins()`
once at startup (idempotent)."""

import importlib
import pkgutil

_loaded = False


def _import_submodules(package_name: str) -> None:
    package = importlib.import_module(package_name)
    for _, name, is_pkg in pkgutil.walk_packages(
        package.__path__, prefix=package.__name__ + "."
    ):
        importlib.import_module(name)
        if is_pkg:
            _import_submodules(name)


def load_builtins() -> None:
    global _loaded
    if _loaded:
        return
    for pkg in ("app.tools.internal", "app.skills", "app.agents"):
        _import_submodules(pkg)
    _loaded = True
